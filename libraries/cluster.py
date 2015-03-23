#!/usr/bin/env python2
# Marco Mravic UCSF Biophysics Kortemme lab W 2015
# Pull_into_place clustering tools
#
# For 06_pick_designs_to_validate.pys
# and condensing final validated designs into 
# most unique sets of designs

import sys,os, numpy as np,itertools, random
from collections import defaultdict

def Score( seq1, seq2, matchDict):
    """
    Helper seqID and substution matrix function
    Input: two ALIGNED sequence strings, ASSUMES aligned and equal length
    Operation: takes max alignment score for both, normalizes actual score by max of two possible
               This is similarity score
    Output: distance = 1-similarity) , 
    """

    ID = score = max1 = max2 = 0.0
    for a,b in zip(seq1,seq2):
        if a==b:   ID+= 1.0/len(seq1)
        score+=matchDict[a][b]
        max1+=matchDict[a][a]
        max2+=matchDict[b][b]

    if score<0: score=0
    # Normalize by length, and highest possible. score
    return 1 - (score/max(max1,max2)), round(ID,3)*100
# 
def seq_variance(seqs_scores):
    """
    Initial assessment of sequence diversity by pairwise sequence ID
    Input: pandas data frame with resFile sequences and pathes
    Operation: randomly samples 5% of all pairwise sequence IDs
    Output: Return mean sequence ID of sample set
    """
    
    # Hardcoded path to Blosum 80  # KALE should integrate this into workspace
    path2matrix='scripts/BLOSUM80'

    # Set up substition matrix
    firstRowFlag=0
    matchDict={}
    r=0
    maxVal=0
    with open(path2matrix) as file:
        for line in file:
            if line[0]=='#': continue
            if firstRowFlag == 0: 
                indices=line.rsplit()
                firstRowFlag+=1
                continue
            matchDict[indices[r]]={}
            k=0
            for i in line.rsplit():
                matchDict[indices[r]][indices[k]]=int(i)
                maxVal = max(int(i), maxVal)
                k+=1

            r+=1

    # Helper function chooses random combinations of sequences
    def random_combination(iterable, r):    
        pool = tuple(iterable)
        n = len(pool)
        indices = sorted(random.sample(xrange(n), r))
        return tuple(pool[i] for i in indices)

    
    # Sample median&mean of 1000 random pairwise comparisons or all possible
    fracCombos=len(seqs_scores['sequence'])*( len(seqs_scores['sequence']) -1)/2
    j=1000
    seqIds=[]
    scores=[]
    if j>fracCombos:
        j=fracCombos

    while j>0:
        objectT= random_combination( enumerate(seqs_scores['sequence']), 2)
        score, seqID = Score( objectT[0][1], objectT[1][1], matchDict ) 
        seqIds.append( seqID )
        scores.append( score )
        j-=1

    seqIds=np.array(seqIds)

    scores=np.array(scores)

    print 
    print 'Sequence ID:  Max, ', round( np.max(seqIds) ,2 ), "; Median, ", round( np.median(seqIds) , 2 ), "; Mean ", round( np.mean(seqIds) , 2 ), "; Std. Dev.: ", round( np.std(seqIds) , 2 )
    print
    print 'Similarity (B80):  Max, ', round( np.max(scores) ,2 ), 'Min, ', round( np.min(scores) ,2 ), "; Median, ", round( np.median(scores) , 2 ), "; Mean ", round( np.mean(scores) , 2 ), "; Std. Dev.: ", round( np.std(scores) , 2 )
    return

def seq_varianceDesigns(designs):
    """
    Initial assessment of sequence diversity by pairwise sequence ID
    Input: pandas data frame with resfile sequences and paths
    Operation: randomly samples 5% of all pairwise sequence IDs
    Output: Return mean sequence ID of sample set
    """
    
    # Hardcoded path to Blosum 80  # KALE should integrate this into workspace
    path2matrix='scripts/BLOSUM80'

    # Set up substitution matrix
    firstRowFlag=0
    matchDict={}
    r=0
    maxVal=0
    with open(path2matrix) as file:
        for line in file:
            if line[0]=='#': continue
            if firstRowFlag == 0: 
                indices=line.rsplit()
                firstRowFlag+=1
                continue
            matchDict[indices[r]]={}
            k=0
            for i in line.rsplit():
                matchDict[indices[r]][indices[k]]=int(i)
                maxVal = max(int(i), maxVal)
                k+=1

            r+=1

    # Manageable array
    sequences=[]
    for i in designs:
        sequences.append(i.sequence)

    # Helper function chooses random combinations of sequences
    def random_combination(iterable, r):    
        pool = tuple(iterable)
        n = len(pool)
        indices = sorted(random.sample(xrange(n), r))
        return tuple(pool[i] for i in indices)
    
    #Sample median&mean of 1000 random pairwise comparisons or all possible
    fracCombos=len(sequences)*(len( sequences) -1)/2
    j=1000
    seqIds=[]
    scores=[]
    if j>fracCombos:
        j=fracCombos
    while j>0:
        objectT= random_combination( enumerate(sequences), 2)
        score, seqID = Score( objectT[0][1], objectT[1][1], matchDict ) 
        seqIds.append( seqID )
        scores.append( score )
        j-=1

    seqIds=np.array(seqIds)
    scores=np.array(scores)
    print 
    print 'Sequence ID:  Max, ', round( np.max(seqIds) ,2 ), "; Median, ", round( np.median(seqIds) , 2 ), "; Mean ", round( np.mean(seqIds) , 2 ), "; Std. Dev.: ", round( np.std(seqIds) , 2 )
    print
    print 'Similarity (B80):  Max, ', round( np.max(scores) ,2 ), 'Min, ', round( np.min(scores) ,2 ), "; Median, ", round( np.median(scores) , 2 ), "; Mean ", round( np.mean(scores) , 2 ), "; Std. Dev.: ", round( np.std(scores) , 2 )
    return



class Cluster:
    """
    Class holding a clustering
    """
    pass


def medoid(listC, cen, memo, matchDict):
    """
    input list and value (list of sequences, and a sequence)
    also input ongoing memo of stored scores, and scoring matrix
    """
    sse=0.0
    for i in listC:
        try:
            dist= memo[ ( i.path, cen.path ) ]
        except KeyError:
            dist=Score( i.sequence, cen.sequence, matchDict)[0]
            memo[ ( i.path, cen.path ) ] = dist
            memo[ ( cen.path, i.path ) ] = dist
        sse += dist

    return  sse, memo


def finalClusters( designs, numClust, dirPath, verbose=False):
    """
    Full clustering of final sequences, post-validation
    This should be < 200-300 sequences, usually more like 50-100
    Can have user-defined cluster number numClust
    numClust=0 default will automatically find the best numClust
    by optimizing the sum of sequared distances in the clusters.
    Here, a matrix of distances is progressively memoized and saved into a pickle 
    file, in case multiple rounds are run (give task name)
    """

    # Hardcoded path to Blosum 80  # KALE should integrate this into workspace
    path2matrix='scripts/BLOSUM80'

    # Read in and store substitution matrix
    firstRowFlag=0
    matchDict={}
    r=0
    flag=0
    maxVal=0
    with open(path2matrix) as file:
        for line in file:
            if line[0]=='#': continue
            if firstRowFlag == 0: 
                indices=line.rsplit()
                firstRowFlag+=1
                continue
            matchDict[indices[r]]={}
            k=0
            for i in line.rsplit():
                matchDict[indices[r]][indices[k]]=int(i)
                maxVal = max(int(i), maxVal)
                k+=1
            r+=1

    # Set number of clusters (initial and the queue)
    if numClust!=0: 
        queue=np.array( [numClust] )
        maxNum = 0   
    else:
        if len(designs) <=50: 
            queue=np.arange( 4,12,1 ) 
        else:
            numClust=int(len(designs)*0.04)
            maxNum=int(len(designs)*0.15)
            queue=np.arange( numClust,maxNum+1,1 )

    # Record distances as you go
    # Matrix map to distance matrix, fill out progressively, can recall
    if os.path.exists(os.path.join( dirPath, 'memoCluster.pkl' ) ):
        memo=pic.load( open( os.path.join( dirPath, 'memoCluster.pkl' ) , 'rb') )
    else:
        memo={}                 
    
    # Score is SSE (Sum of square distances)
    # Distance = 1 - ( normalized similarity score from substitution matrix )
    # track and minimize error (SSE) from medoids
    def kmedoids(numClust, designs, memo):
        copyList = designs[:]

        # Pick initial cluster centers (random), remove from main list, add 
        # self to cluster
        seeds = [ copyList[x] for x in random.sample( xrange(0, len(designs)-1), int(numClust)) ]
        clustering = defaultdict(list)
        for n in seeds:     
            copyList.remove(n)
            clustering[n].append(n)  # Distance to self is 0

        # MAIN LOOP

        boolFlag=True
        while boolFlag:
            sse=0

            # Assign clusters
            for i in copyList:
                trial=[]
                for j in seeds:
                    try:
                        score= memo[ ( i.path, j.path ) ]
                    except KeyError:
                        score=Score( i.sequence, j.sequence, matchDict)[0]
                        memo[ ( i.path, j.path ) ] = score
                        memo[ ( j.path, i.path ) ] = score
                    trial.append( ( score, j ) )
                score, best = sorted(trial)[0]   ## put seq into most similar cluster
                sse += (score)/len(copyList)

                clustering[ best ].append(i)

            #print '\nThis round\'s S.S.E: ',round(sse,3), len(copyList)

            # Re-calc centroid, by minimizing pairwise within cluster 
            new_seeds=[]
            for j,k in clustering.items():
                memo2=[]
            # try each cluster member out as a centroid: calculate it's SSE acting as centroid
                for a in k:
                    sse2, memo = medoid( k , a , memo , matchDict)
                    memo2.append( (round(sse2,3), a ) )
                bestNew=sorted( memo2 )[0][1]
                new_seeds.append( bestNew )

            # End optimization loop if mediods same between iterations
            if sorted(seeds)==sorted(new_seeds):
                boolFlag=False
                return clustering, sse, memo

            seeds=new_seeds
            #print "new:",
            clustering = defaultdict(list)
            copyList=designs[:]
            for n in sorted(seeds): 
                #print n,    
                copyList.remove(n)
                clustering[n].append(n)  # Distance to self is 0


    y=[]

    finalClustering={}
    minSSE=100
    numC=0

    # Loop through each possible cluster size (could be 1 try if user-defined)
    # Try each clustering 1000 times, with random initialization
    # save clustering with minimum SSE, write clustering to text file. 
    for i in queue:

        n=1000

        clusMin=n
        while n>0:

            clustering, sse, memo = kmedoids(i, designs, memo)
            y.append(sse)

            # Global minimum
            if sse<minSSE:
                minSSE=round(sse,4)
                finalClustering=clustering
                numC=i
            # Cluster's minimum sse
            if sse<clusMin:
                clusMin=round(sse,4)
            n-=1
        if verbose: print i, "clusters results in minimum SSE of ", clusMin
        y.append(clusMin)

    if verbose:
        print 
        if maxNum >0: print "Tried", maxNum, "clusters"
        print numC, "Clusters for a minimim Sum of Squared Errors from mediod",minSSE
        print 

    return clustering
