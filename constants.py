import os
import pathlib
import multiprocessing

#
# APPLICATION 
#

DIRECTORY_APPLICATION = str(pathlib.Path.home()) + '/formelbaer'
DIRECTORY_GENERATED_DATA = str(pathlib.Path.home()) + '/formelbaer/generated'
DIRECTORY_ARXIV_DATA = str(pathlib.Path.home()) + '/formelbaer/arxiv'
DIRECTORY_SFB_CLUSTER_ARXIV_DATA = '/rdata/schill/arxiv_processed/all/pngs'

if os.path.exists(DIRECTORY_SFB_CLUSTER_ARXIV_DATA):
	DIRECTORY_ARXIV_DATA = DIRECTORY_SFB_CLUSTER_ARXIV_DATA

if not os.path.exists(DIRECTORY_APPLICATION):
	os.makedirs(DIRECTORY_APPLICATION)

if not os.path.exists(DIRECTORY_GENERATED_DATA):
	os.makedirs(DIRECTORY_GENERATED_DATA)

if not os.path.exists(DIRECTORY_ARXIV_DATA):
	raise ValueError()

ADVERSARIAL_ITERATIONS = 4
ADVERSARIAL_DISCRIMINATOR_STEPS = 2 # (*2) due to implementation
ADVERSARIAL_GENERATOR_STEPS = 1
ADVERSARIAL_SEQUENCE_LENGTH = 6
ADVERSARIAL_MONTECARLO = 6
ADVERSARIAL_PREFERRED_BATCH_SIZE = 32

if multiprocessing.cpu_count() > 15:
	ADVERSARIAL_PREFERRED_BATCH_SIZE = multiprocessing.cpu_count()
	# TODO test with two or three times the amound to justify fork overhead?
	# batch size vs learning rate
	# trade off: more generalization with lower batch size and less accurate gradients

#
# GENERATOR
#

GENERATOR_HIDDEN_DIM = 32
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
