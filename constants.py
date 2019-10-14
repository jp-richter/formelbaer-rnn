import os
import pathlib
import multiprocessing
import logging

#
# APPLICATION 
#

# '/rdata/schill/arxiv_processed/all/pngs'
# '/rdata/schill/equationlearning'

DIRECTORY_APPLICATION = '/ramdisk/formelbaer_data/'
DIRECTORY_SYNTHETIC_DATA = DIRECTORY_APPLICATION + '/synthetic'
DIRECTORY_ARXIV_DATA = DIRECTORY_APPLICATION + '/arxiv'
DIRECTORY_ORACLE_DATA = DIRECTORY_APPLICATION + '/oracle'

FILE_LOG = DIRECTORY_APPLICATION + '/results.log'
FILE_ORACLE = DIRECTORY_APPLICATION + '/oracle.pt'

ADVERSARIAL_ITERATIONS = 2
ADVERSARIAL_DISCRIMINATOR_STEPS = 2 # (*2) due to computational cost reasons
ADVERSARIAL_GENERATOR_STEPS = 1
ADVERSARIAL_SEQUENCE_LENGTH = 16
ADVERSARIAL_MONTECARLO_TRIALS = 16 # seqGan
ADVERSARIAL_BATCHSIZE = multiprocessing.cpu_count()*4

ORACLE = False
ORACLE_SAMPLESIZE = 100

LABEL_SYNTH = 1
LABEL_ARXIV = 0

#
# GENERATOR
#

GENERATOR_HIDDEN_DIM
GENERATOR_LAYERS = 2
GENERATOR_DROPOUT = 0.2
GENERATOR_LEARNRATE = 0.01
GENERATOR_BASELINE = 1
GENERATOR_GAMMA = 0.98

#
# DISCRIMINATOR
#

DISCRIMINATOR_DROPOUT = 0.2
DISCRIMINATOR_LEARNRATE = 0.01
