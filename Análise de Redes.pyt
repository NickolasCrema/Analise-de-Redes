# -*- coding: utf-8 -*-

import arcpy
import os

class Toolbox(object):
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "Toolbox"
        self.alias = "toolbox"

        # List of tool classes associated with this toolbox
        self.tools = [Tool]

class Tool(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Criar Rede"
        self.description = ""
        self.canRunInBackground = False

    def getParameterInfo(self):
        param_feature = arcpy.Parameter(name="Feature", 
        displayName="Malha de linhas", 
        direction="Input", 
        parameterType="Required", 
        datatype="DEFeatureClass", 
        )
        param_workspace = arcpy.Parameter(name="Workspace", 
        displayName="Workspace de saída", 
        direction="Input", 
        parameterType="Required", 
        datatype="DEWorkspace", 
        )
        param_vertex = arcpy.Parameter(name="Vertex", 
        displayName="Nome do arquivo de vértices", 
        direction="Input", 
        parameterType="Required", 
        datatype="GPString", 
        )
        param_edge = arcpy.Parameter(name="Edge", 
        displayName="Nome do arquivo de arestas", 
        direction="Input", 
        parameterType="Required", 
        datatype="GPString", 
        )
        
        return [param_feature, param_workspace, param_vertex, param_edge]

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        parameters = ParametersWrapper(parameters)
        inputFeature = parameters.Feature.valueAsText
        workspace = parameters.Workspace.valueAsText
        vertexFileName = parameters.Vertex.valueAsText
        edgeFileName = parameters.Edge.valueAsText
        vertexPath = workspace + "\\" + vertexFileName
        edgesPath = workspace + "\\" + edgeFileName
        
        scratch = arcpy.env.scratchGDB

        inputSpatialReference = arcpy.Describe(inputFeature).spatialReference
        sr = arcpy.SpatialReference('SIRGAS_2000_UTM_Zone_21S')

        if inputSpatialReference != sr:
            arcpy.management.Project(inputFeature, scratch + '\\inputFeature_project', sr)
            inputFeature = scratch + '\\inputFeature_project'
        spatialReference = arcpy.Describe(inputFeature).spatialReference

        g = Graph(inputFeature)

        arcpy.CreateFeatureclass_management(workspace, edgeFileName, "POLYLINE", spatial_reference=spatialReference)
        arcpy.management.AddField(edgesPath + '.shp', 'Id')
        arcpy.management.AddField(edgesPath + '.shp', 'Start', 'LONG')
        arcpy.management.AddField(edgesPath + '.shp', 'End', 'LONG')

        arcpy.CreateFeatureclass_management(workspace, vertexFileName, "POINT", spatial_reference=spatialReference)
        arcpy.management.AddField(vertexPath + '.shp', 'Id')
        arcpy.management.AddField(vertexPath + '.shp', 'Edges', 'TEXT')


        exploredAll = []
        resultAll = []
        for vertice in g.vertices:
            explored = []
            queue = []
            if vertice not in exploredAll:
                BFS(g, vertice, explored, queue, exploredAll)
                resultVertices = []
                for vertice in explored:
                    edg = []
                    for edge in vertice.edges:
                        edg.append(str(edge.index))

                    resultVertices.append((vertice.shape, vertice.index, ';'.join(edg)))
                
                    resultAll.append(resultVertices)
                explored =[]

        mainGraph = resultAll[0]
        for list in resultAll:
            if len(list) > len(mainGraph):
                mainGraph = list
            else:
                del list
     
        resultEdges = []
   
        list = [int(row[1]) for row in mainGraph]
 
        for edge in g.edges:
            if g.vertices[edge.start.index].index in list:
                resultEdges.append((edge.shape, edge.index, edge.start.index, edge.end.index, edge.length))

        with arcpy.da.InsertCursor(vertexPath, ['SHAPE@', 'Id', 'Edges']) as cursor:
            for vert in mainGraph:
                cursor.insertRow(vert)
        
        with arcpy.da.InsertCursor(edgesPath, ['SHAPE@', 'Id', 'Start', 'End', 'Shape_Length']) as cursor:
            for edge in resultEdges:
                cursor.insertRow(edge)

        arcpy.management.Delete(inputFeature)

        return

def getEdgesFromVertex(vertex):
    concatEdges = []
    for edge in vertex.edges:
        concatEdges.append(str(edge.index))
    return ';'.join(concatEdges)

def endpoints(shape):
    '''Retorna as extremindades de uma linha.'''
    part = shape.getPart(0)
    return (arcpy.PointGeometry(part[0], shape.spatialReference), arcpy.PointGeometry(part[-1], shape.spatialReference))

def pointDistance(A, B):
    return ((A.X - B.X)**2 + (A.Y - B.Y)**2)**0.5

class Graph:
    class Edge:
        def __init__(self, shape):
            self.shape = shape
            self.length = shape.length
            self.start = None
            self.end = None
        
        def __repr__(self):
            return f"({self.index}, {self.start.index} → {self.end.index})"
            
    class Vertex:
        def __init__(self, shape):
            self.shape = shape
            self.index = []
            self.edges = []
        
        @property
        def point(self):
            return self.shape.getPart(0)
        
        def __repr__(self):
            aux = ", ".join(str(i.index) for i in self.edges)
            return f"({self.index}, [{aux}])"
        
    def __init__(self, input_lines_path):
        self.edges = []
        self.vertices = []
        self.create_from_line_feature_class(input_lines_path)
        
    def __len__(self):
        return (len(self.edges), len(self.vertices))
    
    def closestVertex(self, point):
        return min(self.vertices, key = lambda i: pointDistance(i.point, point))
    
    def enumerateStuff(self):
        for i, edge in enumerate(self.edges):
            edge.index = i
        for i, vertex in enumerate(self.vertices):
            vertex.index = i
                
    def updateConnections(self):
        for edge in self.edges:
            A, B = endpoints(edge.shape)
            
            A_vertex = self.closestVertex(A.getPart(0))
            A_distance = pointDistance(A.getPart(0), A_vertex.shape.getPart(0))
            if A_distance > 0.001:
                A_vertex = Graph.Vertex(A)
                self.vertices.append(A_vertex)
            edge.start = A_vertex
            A_vertex.edges.append(edge)
                
            B_vertex = self.closestVertex(B.getPart(0))
            B_distance = pointDistance(B.getPart(0), B_vertex.shape.getPart(0))
            if B_distance > 0.001:
                B_vertex = Graph.Vertex(B)
                self.vertices.append(B_vertex)
            edge.end = B_vertex
            B_vertex.edges.append(edge)
            
    def create_from_line_feature_class(self, input_lines_path):
        self.edges = []
        self.vertices = []
           
        #Camadas Auxiliares
        single_part_lines = os.path.join("memory", "Linhas_Soltinhas")
        output_points = os.path.join("memory", "Intersecoes")
        singlepart_points = os.path.join("memory", "Intersecoes_Single")
        splited_lines = os.path.join("memory", "Linhas_Quebradas")
        
        #Garatir que cada linha seja uma feição
        arcpy.management.MultipartToSinglepart(input_lines_path, single_part_lines)
        #Intersecções entre todas as linhas
        
        arcpy.analysis.PairwiseIntersect(single_part_lines, output_points, "ONLY_FID", None, "POINT")
        arcpy.management.MultipartToSinglepart(output_points, singlepart_points)
        
        #A intersecção gera pontos duplicados... vamos removê-los:
        arcpy.management.DeleteIdentical(singlepart_points, "Shape", "0.1 Meters", 1)
        
        #Divide as linhas nas intersecções
        arcpy.management.SplitLineAtPoint(single_part_lines, singlepart_points, splited_lines, "1 Meters")

        self.edges = list(map(Graph.Edge, (i[0] for i in arcpy.da.SearchCursor(splited_lines, ["SHAPE@"]))))
        self.vertices = list(map(Graph.Vertex, (i[0] for i in arcpy.da.SearchCursor(singlepart_points, ["SHAPE@"]))))
                   
        self.updateConnections()
        self.enumerateStuff()
        
        arcpy.management.Delete(single_part_lines)
        arcpy.management.Delete(output_points)
        arcpy.management.Delete(splited_lines)
        arcpy.management.Delete(singlepart_points)
    
    def __repr__(self):
        return f"{{{self.edges}, {self.vertices}}}"
    
class ParametersWrapper(object):
    """Empacota os parâmetros para permitir acesso por nome."""
    def __init__(self, parameters):
        for p in parameters:
            self.__dict__[p.name] = p

def BFS(graph, root, explored, queue, exploredAll):
    explored.append(root)
    queue.append(root)
    exploredAll.append(root)
    while len(queue) != 0:
        v = queue.pop(0)
        for edge in v.edges:
            if graph.vertices[int(graph.edges[int(edge.index)].end.index)] not in explored:
                explored.append(graph.vertices[int(graph.edges[int(edge.index)].end.index)])
                queue.append(graph.vertices[int(graph.edges[int(edge.index)].end.index)])
                exploredAll.append(graph.vertices[int(graph.edges[int(edge.index)].end.index)])
            if graph.vertices[int(graph.edges[int(edge.index)].start.index)] not in explored:
                explored.append(graph.vertices[int(graph.edges[int(edge.index)].start.index)])
                queue.append(graph.vertices[int(graph.edges[int(edge.index)].start.index)])
                exploredAll.append(graph.vertices[int(graph.edges[int(edge.index)].start.index)])