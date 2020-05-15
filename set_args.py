import argparse

parser = argparse.ArgumentParser(description='End2End Semi-Supervised Lobe Segmentation')


parser.add_argument(
    '-lr',
    '--lr',
    help='learning rate',
    type=float,
    default=0.0001)

parser.add_argument(
    '-load',
    '--load',
    help='load last model',
    type=int,
    default=0)

parser.add_argument(
    '-aux',
    '--aux_output',
    help='Value of Auxiliary Output',
    type=float,
    default=1)

parser.add_argument(
    '-ds',
    '--deep_supervision',
    help='Number of Deep Supervisers',
    type=int,
    default=2)

parser.add_argument(
    '-fn',
    '--feature_number',
    help='Number of initial of conv channels',
    type=int,
    default=16)

parser.add_argument(
    '-bn',
    '--batch_norm',
    help='Set Batch Normalization',
    type=int,
    default=1)

parser.add_argument(
    '-dr',
    '--dropout',
    help='Set Dropout',
    type=int,
    default=1)

parser.add_argument(
    '-trgt_sz',
    '--trgt_sz',
    help='target size',
    type=int,
    default=None)

parser.add_argument(
    '-trgt_z_sz',
    '--trgt_z_sz',
    help='target z size',
    type=int,
    default=None)

parser.add_argument(
    '-trgt_space',
    '--trgt_space',
    help='spacing along x, y ',
    type=float,
    default=1.4)

parser.add_argument(
    '-trgt_z_space',
    '--trgt_z_space',
    help='spacing along z',
    type=float,
    default=2.5)

parser.add_argument(
    '-ptch_sz',
    '--ptch_sz',
    help='patch size',
    type=int,
    default=144)

parser.add_argument(
    '-ptch_z_sz',
    '--ptch_z_sz',
    help='patch z size',
    type=int,
    default=96)

parser.add_argument(
    '-batch_size',
    '--batch_size',
    help='batch_size',
    type=int,
    default=1)

parser.add_argument(
    '-patches_per_scan',
    '--patches_per_scan',
    help='patches_per_scan',
    type=int,
    default=10)

parser.add_argument(
    '-iso',
    '--iso',
    help='do isotropic',
    type=int,
    default=0)

parser.add_argument(
    '-tr_nb',
    '--tr_nb',
    help='nunber of training samples',
    type=int,
    default=5)

args = parser.parse_args()
