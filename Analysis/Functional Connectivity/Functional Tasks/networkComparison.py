#!/usr/bin/env python

"""		
	Purpose of the script:
	----------------------
	The code for computing alignment-free network distances between a set of network given in 
	a folder. 
	
	The script automatically searches all relevant network files for the computation of the 
	network distances in a given folder. 
	
	With the script, the following network distances can be computed:	
		1) GCD distance
		2) RGF Distance
		3) GDD-Agreement with Arithmetic Mean (GDD-A)
		4) GDD-Agreement with Geometric Mean (GDD-G)
		5) Degree Distribution Distance
		6) Average Degree Distance
		7) Average Clustering Coefficient Distance
		8) Diameter Distances of the network
	
	The script outputs the computed distances between all pairs of networks in CSV format
		
	Notes on using the script:
	--------------------------
	
	The script excepts a folder. Using python's os.walk() function, it automatically 
	identifies all networks under the given folder.
	
	Each network files should contain a set of networks (in LEDA format -- ending 
	with extension .gw) and their graphlet degree vector (.ndump2) files.
	
	The code processes them through the following steps:
	
	1) Reads the networks from '.gw' files and the graphlet signatures from '.ndump' files
	2) Depending on the requested distance measure, computes the relevant network properties 
	(e.g., degree distribution, diameter, clustering coefficient) if needed
	3) For computing graphlet degree Compute the log-scaled signatures of all nodes in all files in the folder (log(gd + 1) for all graphlet degrees)
	
	Run as:
		python network_comparison.py <network_folder> <distance_type> <process_count>
		
		<network_folder> : The folder in which all networks are going to be compared.
				Contains the '.ndump2' and '.gw' files of the networks in the cluster
				The content of the networks folder is as follows:
					1) '.ndump2' files - contains the graphlet signatures of all the nodes
					2) '.gw' files - contains the network in LEDA format (required only in <test_mode> == 3)
				The names of the '.gw' files and '.ndump2' files should exactly match.
		
		<distance_type>: 
			'rgf'			- RGF distance
			'gdda'			- GDD Agreement (Both Arithmetic \& Geometric)
			'degree' 		- Degree distribution & Average degree distances
			'clustering'	- Clustering Coefficient
			'diameter' 		- Diameter
			'gcd11'  		- Graphlet Correlation distance with non-redundant 2-to-4 node graphlet orbits
			'gcd15'  		- Graphlet Correlation distance with all 2-to-4 node graphlet orbits
			'gcd58'  		- Graphlet Correlation distance with non-redundant 2-to-5 node graphlet orbits
			'gcd73'  		- Graphlet Correlation distance with all 2-to-5 node graphlet orbits
			'spectral'		- Spectral distance using the eigenvalues of the Laplacian representation of the network
		
		<process_count>:
			Any number higher than or equal to 1. Determines the number of processes to use for computing the 
			distances.
			
	Implemented by:
		Omer Nebil Yaveroglu
		
		First implementation 	= 01.06.2012 - 11:53
		Revision 1 				= 10.08.2012 - 16:48
		Revision 2 				= 23.08.2012 - 11:34
		Parallelized			= 09.10.2012 - 17:00
		Clean Version 			= 06.05.2014 - 15:21
"""

import sys
import os
import math
import numpy
import time
import networkx as nx
import multiprocessing, Queue

from scipy import stats

"""
	Functions
"""

# Read the signatures from ndump2 files
def readSignatures(file):
	signDict = []
	
	fRead = open(file, 'r')
	
	for line in fRead:
		signDict.append([float(value) for value in line.strip().split(' ')[-73:]])
		
	fRead.close()
	
	return signDict

# Remove the redundant orbits and return the log scaled graphlet degrees
def formatSignatures(signList, testMode):
	formattedSignatures = []
	
	for sign in signList:
		# Eliminate the orbits that we are not interested
		if testMode == 16:		# GCD-15
			log = sign[:15]
		elif testMode == 14:	# GCD-73
			log = sign
		elif testMode == 7:		# GCD-58
			eliminateList = [3, 5, 7, 14, 16, 17, 20, 21, 23, 26, 28, 38, 44, 47, 69, 71, 72]
			log = [sign[i] for i in range(73) if i not in eliminateList]
		elif testMode == 10:	# GCD-11
			eliminateList = [3, 12, 13, 14]
			log = [sign[i] for i in range(15) if i not in eliminateList]
		
		formattedSignatures.append(log)
	
	return formattedSignatures

# Compute the correlation matrix without isnan values by adding a dummy signature
def computeCorrelMat(formattedSigns):
	
	length = len(formattedSigns[0])
	
	# Add the dummy signature for some noise
	formattedSigns.append([1] * length)
	
	# Compute the ranking for the Spearman's correlation coefficient computation
	rankList = []
	for i in range(length):
		rankList.append(stats.mstats.rankdata([val[i] for val in formattedSigns]))
		
	correlMat = numpy.corrcoef(rankList, rowvar = 1)
		
	return correlMat


# The parallel reading class to compute the orbit correlation matrices depending on the test mode
class MatrixReader(multiprocessing.Process):
	def __init__(self, work_queue, result_queue, testMode):
		multiprocessing.Process.__init__(self)
		
		self.work_queue 	= work_queue
		self.result_queue 	= result_queue
		self.testMode 		= testMode
		self.kill_received 	= False
		
	
	def run(self):
		while not self.kill_received:
			# Get a task
			try:
				ndumpName = self.work_queue.get_nowait()
				
				signatures = readSignatures('{0}.ndump2'.format(ndumpName))
				formatted = formatSignatures(signatures, self.testMode)				
				correlMat = computeCorrelMat(formatted)
								
				self.result_queue.put((ndumpName, correlMat))
				
			except Queue.Empty:
				pass
			

# Computes the orbit correlation matrices for all the correlation matrices provided in allIndexes 
def getCorrelationMatrices(allIndexes, testMode):
	# Prepare the list of files to be processed
	file_queue = multiprocessing.Queue()
	result_queue = multiprocessing.Queue()
	
	processList = []
	for i in range(num_processes):
		reader = MatrixReader(file_queue, result_queue, testMode)
		reader.start()
		processList.append(reader)
	
	# Put the jobs to be consumed
	jobCount = len(allIndexes)
	submitCount = 0
	
	for index in allIndexes:
		file_queue.put(index)
		submitCount += 1
		
		#if submitCount % 100 == 0:
		#	print 'Submitted correlation computation for: ' , str(float(submitCount) / jobCount * 100) , '%'

	# Process the results of computation
	correlMats = {}
	
	finishedCount = 0
	while finishedCount < len(allIndexes):
		try:
			matrix = result_queue.get_nowait()
			correlMats[matrix[0]] = matrix[1]
			finishedCount += 1
		except Queue.Empty:
			time.sleep(1)
		
		#if finishedCount % 100 == 0:
		#	print 'Finished reading: ', str(float(finishedCount) / jobCount * 100) , '%'
	
	for proc in processList:
		proc.terminate()
	
	return correlMats

# Computes the euclidean distance between two correlation matrices
def computeMatrixDist(matrix1, matrix2):
	differenceSum = 0
	
	for i in range(len(matrix1) - 1):
		for j in range( i + 1 , len(matrix1)):
			differenceSum += pow(matrix1[i][j] - matrix2[i][j], 2)
	
	eucDist = math.sqrt(differenceSum)
	
	return eucDist

# The parallel reading class to compute the orbit correlation distances
class correlDistanceComputer(multiprocessing.Process):
	def __init__(self, work_queue, result_queue):
		multiprocessing.Process.__init__(self)
		
		self.work_queue = work_queue
		self.result_queue = result_queue
		self.kill_received = False
	
	def run(self):
		while not self.kill_received:
			# Get a task
			try:
				# matrixPair : 0,1 holds names; 2, 3 holds matrices
				matrixPair = self.work_queue.get_nowait()
				distance = computeMatrixDist(matrixPair[2], matrixPair[3])
				self.result_queue.put((matrixPair[0], matrixPair[1], distance))
			except Queue.Empty:
				pass


# Given a matrix, writes the matrix with the network names into the output file
def saveDistanceMatrix(matrix, networkNames, outputFile):
	fWrite = open(outputFile, 'w')
	
	# Write the names of the networks
	toWrite = '\t'
	for name in networkNames:
		toWrite += name + '\t'
	fWrite.write(toWrite.rstrip() + '\n')
	
	# Write the distances among networks
	for i in range(len(networkNames)):
		toWrite = networkNames[i] + '\t'
		for val in matrix[i]:
			toWrite += str(val) + '\t'
		fWrite.write(toWrite.rstrip() + '\n')
	
	fWrite.close()

# The function to compute all the distances between the provided correlation matrices in parallel
def computeCorrelDist(corrMats, outputName):
	# Start the processes
	pair_queue = multiprocessing.Queue()
	result_queue = multiprocessing.Queue()
	processList = []
	
	for i in range(num_processes):
		computer = correlDistanceComputer(pair_queue, result_queue)
		computer.start()
		processList.append(computer)
	
	# Put the jobs to be consumed
	totalJobCount = len(corrMats) * (len(corrMats) - 1) / 2
	matList = corrMats.keys()
	matValList = [corrMats[mat] for mat in matList]
	
	pairCount = 0
	for i in range(len(matValList) - 1):
		corrMat1 = matValList[i]
		
		for j in range(i+1, len(matValList)):
			corrMat2 = matValList[j]
			
			pair_queue.put((i, j, corrMat1, corrMat2))
			pairCount += 1
	
	# Consume the results of completed computation
	distances = [[0] * len(corrMats) for i in range(len(corrMats))]
	
	computedCount = 0
	while computedCount < pairCount:
		try:
			results = result_queue.get_nowait()
			distances[results[0]][results[1]] = results[2] 
			distances[results[1]][results[0]] = results[2]
			computedCount += 1
		except Queue.Empty:
			time.sleep(1)
		
	for proc in processList:
		proc.terminate()
	
	# Save the results in the output file
	saveDistanceMatrix(distances, matList, outputName)

# Function to compute the graphlet counts from ndump2 files
def getGraphletFreq(signList):
	orbits = [2, 3, 5, 7, 8, 9, 12, 14, 17, 18, 23, 25, 27, 33, 34, 35, 39, 44, 45, 50, 52, 55, 56, 61, 62, 65, 69, 70, 72]
	weights = [1, 3, 2, 1, 4, 1, 2, 4, 1, 1, 1, 1, 1, 1, 5, 1, 1, 1, 1, 2, 1, 2, 1, 1, 1, 1, 1, 2, 5]
	
	# Derive the graphlet counts from the orbit degrees
	graphletCounts = []
	
	for i in range(len(orbits)):
		orbit = orbits[i]
		sumCount = sum([val[orbit] for val in signList])
		graphletCounts.append(sumCount / weights[i])
	
	return graphletCounts

# Normalize and scale the graphlet distributions for the computation of GDD Agreement
def scaleGraphletDists(signatures):
	distributions = []
	
	for i in range(73):
		# Get the distribution
		values = {}
		for val in signatures:
			try:
				values[val[i]] += 1
			except:
				values[val[i]] = 1
	
		try:
			del(values[0])
		except:
			pass
		
		# Scale the distribution values for GDD agreement
		total = 0
		for val in values:
			values[val] = float(values[val]) / val
			total += values[val]
	
		# Normalize the distributions
		for val in values:
			values[val] /= total
			
		distributions.append(values)
	
	return distributions

# Write the distributions for the network
def writeDistributions(outputName, distribution):
	fWrite = open(outputName, 'w')
	
	i = 0
	
	for dictin in distribution:
		toPrint = ''
		
		for val in dictin:
			toPrint += str(val) + '_' + str(dictin[val]) + ','
		
		fWrite.write(toPrint.rstrip(',') + '\n')
		i += 1
	
	
	fWrite.close()

# The parallel running class for reading the graphlet counts from ndump files
class GraphletCountGetter(multiprocessing.Process):
	def __init__(self, work_queue, result_queue, mode):
		multiprocessing.Process.__init__(self)
		
		self.work_queue = work_queue
		self.result_queue = result_queue
		self.mode = mode
		self.kill_received = False
	
	def run(self):
		while not self.kill_received:
			# Get a task
			try:
				ndumpName = self.work_queue.get_nowait()
				
				signatures = readSignatures('{0}.ndump2'.format(ndumpName))
			
				if self.mode == 1:
					counts = getGraphletFreq(signatures)
					self.result_queue.put((ndumpName, counts))
				elif self.mode == 2:
					dists = scaleGraphletDists(signatures)
					writeDistributions(ndumpName, dists)
					self.result_queue.put(1)
			except:
				pass
			
			

# The function reads the graphlet signatures in parallel and computes the graphlet counts 
def getGraphletDists(allIndexes, mode):
	# Start the processes
	file_queue = multiprocessing.Queue()
	result_queue = multiprocessing.Queue()
	
	processList = []
	for i in range(num_processes):
		reader = GraphletCountGetter(file_queue, result_queue, mode)
		reader.start()
		processList.append(reader)
	
	# Put the jobs to be consumed
	jobCount = len(allIndexes)
	submittedCount = 0
	for index in allIndexes:
		file_queue.put(index)
		submittedCount += 1
		
		#if submittedCount % 100 == 0:
		#	print 'Distribution Getter Jobs submitted: ' , str(float(submittedCount) / jobCount * 100) , '%'
	
	# Process the results of computation
	grCounts = {}
	
	finishedCount = 0
	while finishedCount < len(allIndexes):
		try:
			counts = result_queue.get_nowait()
			if mode == 1:
				grCounts[counts[0]] = counts[1]
			finishedCount += 1
		except Queue.Empty:
			time.sleep(1)
		
		#if finishedCount % 100 == 0:
		#	print 'Distributions obtained for:' , str(float(finishedCount) / jobCount * 100) , '%'
	
	for proc in processList:
		proc.terminate()
	
	return grCounts

# Compute the RGF distance among two signatures
def computeRGFDist(signs1, signs2):
	# Compute the distance
	T1 = sum(signs1)
	T2 = sum(signs2)
	
	if T1 == 1:
		T1 = 1.0000000001
	if T2 == 1:
		T2 = 1.0000000001
		
	for i in range(len(signs1)):
		if signs1[i] <> 0:
			signs1[i] = (-1 * math.log(signs1[i])) / math.log(T1)
	
	for i in range(len(signs1)):
		if signs2[i] <> 0:
			signs2[i] = (-1 * math.log(signs2[i])) / math.log(T2)
	
	distance = 0
	for i in range(29):
		distance += abs(signs1[i] - signs2[i])
	
	return distance

# Reads the previously saved graphlet degree distribution files
def readDist(fileName):
	
	dists = []
		
	fRead = open(fileName, 'r')
	for line in fRead:
		dictin = {}
		
		if line.strip() <> '':
			line_splitted = line.strip().split(',') 

			for tuple in line_splitted:
				splitted = tuple.split('_')
				dictin[float(splitted[0])] = float(splitted[1])
				
		dists.append(dictin)
		
	fRead.close()
	
	return dists

# Compute the GDD agreement among two networks
def computeGDDAgreement(index1, index2):
	# Compute the distributions for each orbit (for both networks)
	orbitDist = []
		
	signs1 = readDist(index1)
	signs2 = readDist(index2)
	
	
	for i in range(73):
		values1 = signs1[i]
		values2 = signs2[i]
		
		# Compute the distance among the orbits
		sumDistances = 0
		allDegrees = list(set(values1.keys()) | set(values2.keys()))
		for val in allDegrees:
			try:
				score1 = values1[val]
			except:
				score1 = 0
			
			try:
				score2 = values2[val]
			except:
				score2 = 0
			
			sumDistances += ((score1 - score2)  ** 2)
		
		orbitDist.append(1 - ((1/math.sqrt(2)) * math.sqrt(sumDistances)) )
	
	gdda_distance = numpy.mean(orbitDist)
	gddg_distance = stats.gmean(orbitDist)
	
	return [gdda_distance, gddg_distance]

# The parallel reading class to compute the orbit correlation distances
class GraphletDistComputer(multiprocessing.Process):
	def __init__(self, work_queue, result_queue, mode):
		multiprocessing.Process.__init__(self)
		
		self.work_queue = work_queue
		self.result_queue = result_queue
		self.mode = mode
		self.kill_received = False
		
	
	def run(self):
		while not self.kill_received:
			# Get a task
			try:
				# matrixPair : 0,1 holds names; 2, 3 holds distributions
				matrixPair = self.work_queue.get_nowait()
								
				if self.mode == 1:
					rgf = computeRGFDist(matrixPair[2], matrixPair[3])
					self.result_queue.put((matrixPair[0], matrixPair[1], rgf))
				elif self.mode == 2:
					[gdda, gddg] = computeGDDAgreement(matrixPair[2], matrixPair[3])
					self.result_queue.put((matrixPair[0], matrixPair[1], 1 - gdda, 1 - gddg))
			except:
				pass
			

# Compute the RGF Distances among all pairs of networks
def computeRGFDistances(graphletCounts, outputName):
	# Start the processes
	pair_queue = multiprocessing.Queue()
	result_queue = multiprocessing.Queue()
	processList = []
	
	for i in range(num_processes):
		computer = GraphletDistComputer(pair_queue, result_queue, 1)
		computer.start()
		processList.append(computer)
	
	# Put the jobs to be consumed
	jobCount = len(graphletCounts) * (len(graphletCounts) - 1) / 2
	pairCount = 0
	for i in range(len(graphletCounts) - 1):
		dist1 = graphletCounts.values()[i]
		
		for j in range(i+1, len(graphletCounts)):
			dist2 = graphletCounts.values()[j]
			pair_queue.put((i, j, dist1, dist2))
			pairCount += 1
		
		if pairCount % 1000 == 0:
			print 'RGF Comparison Jobs submitted: ' , str(float(pairCount) / jobCount * 100), '%'
	
	# Process the results of computation
	distances = [[0] * len(graphletCounts) for i in range(len(graphletCounts))]
	
	finishedCount = 0
	while finishedCount < pairCount:
		try:
			results = result_queue.get_nowait()
			distances[results[0]][results[1]] = distances[results[1]][results[0]] = results[2]
			finishedCount += 1
		except Queue.Empty:
			time.sleep(1)
		
		if finishedCount % 1000 == 0:
			print 'RGF Distance comparisons finished: ', str(float(finishedCount) / jobCount * 100), '%'
	
	for proc in processList:
		proc.terminate()
	
	# Save the results in the output file
	saveDistanceMatrix(distances, graphletCounts.keys(), outputName)

# The process that consumes the computed results to form the final matrix
class FinishedConsumer(multiprocessing.Process):
	def __init__(self, computed_queue, result_queue, jobCount, elementCount):
		multiprocessing.Process.__init__(self)
		
		self.computed_queue = computed_queue
		self.result_queue = result_queue
		self.jobCount = jobCount
		self.elementCount = elementCount
		self.kill_received = False
		
	
	def run(self):
		gdda_dists = [[0] * self.elementCount for i in range(self.elementCount)]
		gddg_dists = [[0] * self.elementCount for i in range(self.elementCount)]
				
		finishedCount = 0
		while finishedCount < self.jobCount:
			try:
				results = self.computed_queue.get()
				gdda_dists[results[0]][results[1]] = results[2]
				gdda_dists[results[1]][results[0]] = results[2]
				gddg_dists[results[0]][results[1]] = results[3]
				gddg_dists[results[1]][results[0]] = results[3]
				finishedCount += 1
			except Queue.Empty:
				pass
			
			if finishedCount % 1000 == 0:
				print 'Computation completion: ', str(float(finishedCount) / self.jobCount * 100) , '%'
		
		self.result_queue.put((gdda_dists, gddg_dists))
		

# Compute the GDD Agreements between all network pairs
def computeGDDAgreements(graphletCounts, outputName):
	# Start the processes - as consumers of pair_queue
	pair_queue = multiprocessing.Queue()
	result_queue = multiprocessing.Queue()
	summary_queue = multiprocessing.Queue()
	processList = []
	
	for i in range(num_processes):
		computer = GraphletDistComputer(pair_queue, result_queue, 2)
		computer.start()
		processList.append(computer)
	
	jobCount = len(graphletCounts) * (len(graphletCounts) - 1) / 2
	summarizer = FinishedConsumer(result_queue, summary_queue, jobCount, len(graphletCounts))
	summarizer.start()
	
	# Put the jobs in the queue
	pairCount = 0
	for i in range(len(graphletCounts) - 1):
		name1 = graphletCounts[i]
		
		for j in range(i+1, len(graphletCounts)):
			name2 = graphletCounts[j]
			
			pair_queue.put((i, j, name1, name2))
			pairCount += 1
						
	# Wait for the termination of summarizer and get the results from that
	results = summary_queue.get()
	gdda_dists = results[0]
	gddg_dists = results[1]
	
	# Process the results of computation
	for proc in processList:
		proc.terminate()
	
	# Save the results in the output file
	saveDistanceMatrix(gdda_dists, graphletCounts, os.path.join(outputName,'gdda.txt'))
	saveDistanceMatrix(gddg_dists, graphletCounts, os.path.join(outputName,'gddg.txt'))


# The function to read a LEDA formatted network file
def readLeda(networkFile):
	network = nx.Graph()
	
	fRead = open(networkFile, 'r')
	
	mode = 0
	listOfNodes = []
	
	for line in fRead:
		line = line.strip()
		
		if(mode == 0):
			if line.startswith('|'):
				mode = 1
		
		if (mode == 1):
			if line.startswith('|'):
				nodeName = line.strip('|').strip('{').strip('}')
				listOfNodes.append(nodeName)
			else:
				mode = 2
				continue
		
		if (mode == 2):
			splitted = line.split(' ')
			
			node1 = int(splitted[0]) - 1
			node2 = int(splitted[1]) - 1
			
			network.add_edge(node1, node2)
	
	fRead.close()
	
	return network

# The parallel reading class for computing the requested network properties
class NetworkPropertyGetter(multiprocessing.Process):
	def __init__(self, work_queue, result_queue, mode):
		multiprocessing.Process.__init__(self)
		
		self.work_queue = work_queue
		self.result_queue = result_queue
		self.mode = mode
		self.kill_received = False
	
	def run(self):
		while not self.kill_received:
			# Get a task
			try:
				ndumpName = self.work_queue.get_nowait()
				
				network = readLeda(ndumpName + '.gw')
			
				if self.mode == 4:
					prop1	= nx.degree_histogram(network)
					prop2	= numpy.mean(network.degree().values())
					netProp = (prop1, prop2)
				elif self.mode == 5:
					netProp = nx.average_clustering(network)
				elif self.mode == 6:
					largestComp = list(nx.connected_component_subgraphs(network))[0]
					netProp = nx.diameter(largestComp)
				
				self.result_queue.put((ndumpName, netProp))
			except Queue.Empty:
				pass
			
			


	
# Given a network file, reads the networks and computes the relevant network properties (that is defined by mode)
def computeNetworkProperties(allIndexes, mode):
	
	# Start the processes
	file_queue = multiprocessing.Queue()
	result_queue = multiprocessing.Queue()
	
	processList = []
	for i in range(num_processes):
		reader = NetworkPropertyGetter(file_queue, result_queue, mode)
		reader.start()
		processList.append(reader)
	
	# Put the jobs to be consumed
	jobCount = len(allIndexes)
	submitCount = 0
	for index in allIndexes:
		file_queue.put(index)
		submitCount += 1
		
		if submitCount % 100 == 0:
			print 'Network Property Jobs Submitted:', str(float(submitCount) / jobCount * 100) , '%'
		
	
	# Process the results of computation
	properties = {}
	
	finishedCount = 0
	while finishedCount < len(allIndexes):
		try:
			props = result_queue.get_nowait()
			properties[props[0]] = props[1]
			finishedCount += 1
		except Queue.Empty:
			time.sleep(1)
		
		if finishedCount % 100 == 0:
			print 'Ready Network Properties:', str(float(finishedCount) / jobCount * 100) , '%'
	
	for proc in processList:
		proc.terminate()
	
	return properties
	
# Evaluate whether the two distributions are sampled from the same continuous distribution
def compareDistributions(dist1, dist2):
	# Take the euclidean distance of normalized distributions as in GDD agreement
	normDist1 = [float(dist1[i]) / i for i in range(1, len(dist1))]
	normDist2 = [float(dist2[i]) / i for i in range(1, len(dist2))]
	N1 = sum(normDist1)
	N2 = sum(normDist2)
	compLength = max(len(dist1), len(dist2))
	
	sumDif = 0
	for i in range(1, compLength):
		try:
			norm1 = float(normDist1[i]) / N1
		except:
			norm1 = 0
		
		try:
			norm2 = float(normDist2[i]) / N2
		except:
			norm2 = 0
			
		sumDif += ( norm1 - norm2 ) ** 2
	
	dist = math.sqrt(sumDif)
	
	return dist

# The parallel reading class to compute the orbit correlation distances
class PropertyComparer(multiprocessing.Process):
	def __init__(self, work_queue, result_queue, mode):
		multiprocessing.Process.__init__(self)
		
		self.work_queue = work_queue
		self.result_queue = result_queue
		self.mode = mode
		self.kill_received = False
		
	
	def run(self):
		while not self.kill_received:
			# Get a task
			try:
				# matrixPair : 0,1 holds names; 2, 3 holds distributions
				matrixPair = self.work_queue.get_nowait()
				
				if self.mode == 1: # Compare degree distribution and average degree
					dist1 = compareDistributions(matrixPair[2][0], matrixPair[3][0])
					dist2 = math.fabs(matrixPair[2][1] - matrixPair[3][1])
					self.result_queue.put((matrixPair[0], matrixPair[1], (dist1, dist2)))
					
				elif self.mode == 2: # Compare either absolute difference of clustering coef or diameters
					dist = math.fabs(matrixPair[2]- matrixPair[3])
					self.result_queue.put((matrixPair[0], matrixPair[1], dist))
				
			except:
				pass


# Given a set of network properties, computes the distance from them
def compareNetworkProps(propertyList, distanceMode, outputNames):
	# Start the processes
	pair_queue = multiprocessing.Queue()
	result_queue = multiprocessing.Queue()
	
	processList = []
	for i in range(num_processes):
		computer = PropertyComparer(pair_queue, result_queue, distanceMode)
		computer.start()
		processList.append(computer)
	
	# Put the jobs to be consumed
	jobCount = len(propertyList) * (len(propertyList) - 1) / 2
	pairCount = 0
	for i in range(len(propertyList) - 1):
		dist1 = propertyList.values()[i]
		
		for j in range(i+1, len(propertyList)):
			dist2 = propertyList.values()[j]
			
			pair_queue.put((i, j, dist1, dist2))
			pairCount += 1
			
			if pairCount % 1000 == 0:
				print 'Jobs submitted:', str(float(pairCount) / jobCount * 100) , '%'
	
	# Process the results of computation
	distances = [[0] * len(propertyList) for i in range(len(propertyList))]
	if distanceMode == 1:
		dists2 = [[0] * len(propertyList) for i in range(len(propertyList))]
	
	finishedCount = 0 
	while finishedCount < pairCount:
		
		try:
			results = result_queue.get_nowait()
			
			if distanceMode == 1:
				distances[results[0]][results[1]] = distances[results[1]][results[0]] = results[2][0]
				dists2[results[0]][results[1]] = dists2[results[1]][results[0]] = results[2][1]
			else:
				distances[results[0]][results[1]] = distances[results[1]][results[0]] = results[2]
			finishedCount += 1
		except Queue.Empty:
			time.sleep(1)
		
		if finishedCount % 1000 == 0:
			print 'Finished comparisons: ' , str(float(finishedCount) / jobCount * 100) ,  '%'
		
	for proc in processList:
		proc.terminate()
	
	# Save the results in the output file
	if distanceMode == 1:
		saveDistanceMatrix(distances, propertyList.keys(), outputNames[0])
		saveDistanceMatrix(dists2, propertyList.keys(), outputNames[1])
	else:
		saveDistanceMatrix(distances, propertyList.keys(), outputNames)
	
	
# Removes the normalizes distribution files
def cleanTempFiles(fileList):
	for file in fileList:
		os.remove(file)


# The parallel reading class for computing the requested network properties
class SpectrumGetter(multiprocessing.Process):
	def __init__(self, work_queue, result_queue):
		multiprocessing.Process.__init__(self)
		
		self.work_queue = work_queue
		self.result_queue = result_queue
		self.kill_received = False
	
	def run(self):
		while not self.kill_received:
			# Get a task
			try:
				ndumpName = self.work_queue.get_nowait()
				
				network = readLeda('{0}.gw'.format(ndumpName))
				spectrum = sorted(nx.laplacian_spectrum(network), reverse = True)
				
				self.result_queue.put((ndumpName, spectrum))
			except Queue.Empty:
				pass
			
	
	
# Given a network file, reads the networks and computes the relevant network properties (that is defined by mode)
def getSpectralSignatures(allIndexes):
	
	# Start the processes
	file_queue = multiprocessing.Queue()
	result_queue = multiprocessing.Queue()
	
	processList = []
	for i in range(num_processes):
		reader = SpectrumGetter(file_queue, result_queue)
		reader.start()
		processList.append(reader)
	
	# Put the jobs to be consumed
	jobCount = len(allIndexes)
	submitCount = 0
	for index in allIndexes:
		file_queue.put(index)
		submitCount += 1
		
		if submitCount % 100 == 0:
			print 'Spectrum Computation Jobs Submitted:', str(float(submitCount) / jobCount * 100) , '%'
		
	
	# Process the results of computation
	spectrums = {}
	
	finishedCount = 0
	while finishedCount < len(allIndexes):
		try:
			specs = result_queue.get_nowait()
			spectrums[specs[0]] = specs[1]
			finishedCount += 1
		except Queue.Empty:
			time.sleep(1)
		
		if finishedCount % 100 == 0:
			print 'Ready Spectrums:', str(float(finishedCount) / jobCount * 100) , '%'
	
	for proc in processList:
		proc.terminate()
	
	return spectrums
	
# The parallel reading class to compute the orbit correlation distances
class SpectrumComparer(multiprocessing.Process):
	def __init__(self, work_queue, result_queue):
		multiprocessing.Process.__init__(self)
		
		self.work_queue = work_queue
		self.result_queue = result_queue
		self.kill_received = False
		
	
	def run(self):
		while not self.kill_received:
			# Get a task
			try:
				# matrixPair : 0,1 holds names; 2, 3 holds distributions
				matrixPair = self.work_queue.get_nowait()
				
				if len(matrixPair[2]) >= len(matrixPair[3]):
					spec1 = matrixPair[2]
					spec2 = matrixPair[3]
				else:
					spec1 = matrixPair[3]
					spec2 = matrixPair[2]
				
				specDistSum = 0
				for i in range(len(spec1)):
					if i < len(spec2):
						specDistSum += (spec1[i]-spec2[i]) ** 2
					else:
						specDistSum += spec1[i] ** 2
						
				specDist = math.sqrt(specDistSum)
				
				self.result_queue.put((matrixPair[0], matrixPair[1], specDist))
				
			except:
				pass
	
	
# Given a set of network properties, computes the distance from them
def computeSpectralDists(propertyList, outputName):
	# Start the processes
	pair_queue = multiprocessing.Queue()
	result_queue = multiprocessing.Queue()
	
	processList = []
	for i in range(num_processes):
		computer = SpectrumComparer(pair_queue, result_queue)
		computer.start()
		processList.append(computer)
	
	# Put the jobs to be consumed
	jobCount = len(propertyList) * (len(propertyList) - 1) / 2
	spectList = propertyList.keys()
	spectValues = [propertyList[key] for key in spectList]
	
	pairCount = 0
	for i in range(len(propertyList) - 1):
		dist1 = spectValues[i]
		
		for j in range(i+1, len(propertyList)):
			dist2 = spectValues[j]
			
			pair_queue.put((i, j, dist1, dist2))
			pairCount += 1
			
	# Process the results of computation
	distances = [[0] * len(propertyList) for i in range(len(propertyList))]
	
	finishedCount = 0 
	while finishedCount < pairCount:
		
		try:
			results = result_queue.get_nowait()
			distances[results[0]][results[1]] = results[2]
			distances[results[1]][results[0]] = results[2]
			finishedCount += 1
		except Queue.Empty:
			time.sleep(1)
		
	for proc in processList:
		proc.terminate()
	
	# Save the results in the output file
	saveDistanceMatrix(distances, spectList, outputName)

# The function to check whether the provided input parameters are meaningful
def checkInput(ndumpFolder, distType, num_processes):
	if not os.path.isdir(ndumpFolder):
		print 'ERROR: Provided network folder path is not found: {0}'.formaT(ndumpFolder)
		exit(0)
	
	if num_processes < 1:
		print 'ERROR: Enter a correct number for the number of processes...'
		exit(0)

	# For backwards compatibility with original script, map the distType to corresponding testMode number
	testMode = None
	if distType == 'rgf':
		testMode = 2
	elif distType == 'gdda':
		testMode = 3
	elif distType == 'degree':
		testMode = 4
	elif distType == 'clustering':
		testMode = 5
	elif distType == 'diameter':
		testMode = 6
	elif distType == 'gcd58':
		testMode = 7
	elif distType == 'gcd11':
		testMode = 10
	elif distType == 'gcd73':
		testMode = 14
	elif distType == 'gcd15':
		testMode = 16
	elif distType == 'spectral':
		testMode = 17
	else:
		print 'ERROR: Unknown network distance type: {0}'.format(distType)
		print 'Available options are:'
		print 'rgf			- RGF distance'
		print 'gdda			- GDD Agreement (Both Arithmetic \& Geometric)'
		print 'degree 		- Degree distribution & Average degree distances'
		print 'clustering	- Clustering Coefficient'
		print 'diameter 	- Diameter'
		print 'gcd11  		- Graphlet Correlation distance with non-redundant 2-to-4 node graphlet orbits'
		print 'gcd15  		- Graphlet Correlation distance with all 2-to-4 node graphlet orbits'
		print 'gcd58  		- Graphlet Correlation distance with non-redundant 2-to-5 node graphlet orbits'
		print 'gcd73  		- Graphlet Correlation distance with all 2-to-5 node graphlet orbits'
		print 'spectral		- Spectral distance using the eigenvalues of the Laplacian representation of the network'
		exit(0)
	
	return testMode

# The function to search the given folder for ndump2 files
def searchFolder(ndumpFolder, testMode):

	# Identify all files under the folder
	directory 	= os.walk(ndumpFolder)
	
	# Pick the relevant files based on ndump2 extensions
	allIndexes	= []
	for file in directory:
		path = file[0]
		
		for fileName in file[2]:
			if fileName.endswith('.ndump2'):
				stripName = fileName.rsplit('.', 1)[0]
				indexName = os.path.join(path, stripName)
				
				# Read networks for tests 4, 5, 6
				if testMode in [4, 5 ,6, 17]  and stripName + '.gw' not in file[2]:
					print 'ERROR: Network file - Ndump file mismatch!'
					print 'Check: {0}.gw'.format(indexName)
					exit(0)
				
				allIndexes.append(indexName)
				
	return allIndexes
	
"""
	Main code starts here
"""
if __name__ == "__main__":
	# Process the program parameters
	ndumpFolder 	= sys.argv[1]
	distType		= sys.argv[2]
	num_processes	= int(sys.argv[3])
		
	# Due to backward compatibility, map the distance type to corresponding testMode
	testMode  		= checkInput(ndumpFolder, distType, num_processes) 
	
	# Identify the files based on the 'ndump2' extensions	
	allIndexes  	= searchFolder(ndumpFolder, testMode)
	
	
	# Compute the graphlet correlation distance (whatever type it is)
	if testMode in [7, 10, 14, 16]:
		corrMats = getCorrelationMatrices(allIndexes, testMode)
		print 'GCMs are ready! Computing the GCDs...'		
		computeCorrelDist(corrMats, os.path.join(ndumpFolder, '{0}.txt'.format(distType)))
	
	# Compute the spectral distances
	elif testMode == 17:
		# Compute the spectral distance of laplacian
		spectralSigns = getSpectralSignatures(allIndexes)
		print 'Spectral Signatures are ready! Computing the distances...'
		computeSpectralDists(spectralSigns, os.path.join(ndumpFolder, 'spectralDist.txt'))
		
	# Compute the RGF Distance
	elif testMode == 2:
		graphletCounts = getGraphletDists(allIndexes, 1)
		print 'Graphlet Counts ready! Computing the distances...'
		computeRGFDistances(graphletCounts, os.path.join(ndumpFolder, 'rgf.txt'))
		
	# Compute the GDD-Agreement with Arithmetics and Geometric mean
	elif testMode == 3:
		getGraphletDists(allIndexes, 2)
		print 'Graphlet Distributions ready! Computing the distances...'
		computeGDDAgreements(allIndexes, ndumpFolder)
		cleanTempFiles(allIndexes)
		
	# Compute the degree based distance measures
	elif testMode == 4:
		degreeDists = computeNetworkProperties(allIndexes, 4)
		print 'Degree Distributions ready! Computing the distances...'
		compareNetworkProps(degreeDists, 1, [os.path.join(ndumpFolder, 'degree_dists.txt') , os.path.join(ndumpFolder, 'av_degree.txt')])
		
	# Compute the clustering coefficient based distance measures
	elif testMode == 5:
		clustCoefs = computeNetworkProperties(allIndexes, 5)
		print 'Clustering Coefficients ready! Computing the distances...'
		compareNetworkProps(clustCoefs, 2, os.path.join(ndumpFolder, 'clust_coef.txt'))
		
	# Compute the diameter based distance measures
	elif testMode == 6:
		diameters = computeNetworkProperties(allIndexes, 6)
		print 'Diameters ready! Computing the distances...'
		compareNetworkProps(diameters, 2, os.path.join(ndumpFolder, 'diameter.txt'))
	