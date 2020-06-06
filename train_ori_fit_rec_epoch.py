# -*- coding: utf-8 -*-
"""
Main file to train the model.
=============================================================
Created on Tue Apr  4 09:35:14 2017
@author: Jingnan
"""

import numpy as np
# import matplotlib.pyplot as plt
from futils.dataloader import TwoScanIterator
import os

import tensorflow as tf
from tensorflow.keras.utils import GeneratorEnqueuer
from tensorflow.keras import backend as K
from tensorflow.keras import callbacks
from tensorflow.keras.utils import plot_model
from futils import compiled_models as cpmodels

from set_args import args
from write_dice import write_dices_to_csv
from write_batch_preds import write_preds_to_disk
import segmentor as v_seg
from mypath import Mypath

os.environ['CUDA_VISIBLE_DEVICES'] = "0" # use the first GPU
tf.keras.mixed_precision.experimental.set_policy('infer') # mix precision training

config = tf.ConfigProto()
config.gpu_options.allow_growth = True  # dynamically grow the memory used on the GPU
sess = tf.Session(config=config)
K.set_session(sess)  # set this TensorFlow session as the default session for Keras

K.set_learning_phase(1)  # try with 1


def get_task_list(model_names):
    """
    get task list according to a list of model names. one task may corresponds to multiple models.
    :param model_names: a list of model names
    :return: a list of tasks
    """

    net_task_dict = {
        "net_itgt_lobe_recon": "lobe",
        "net_itgt_vessel_recon": "vessel",
        "net_itgt_lung_recon": "lung",
        "net_itgt_airway_recon": "airway",

        "net_no_label": "no_label",

        "net_only_lobe": "lobe",
        "net_only_vessel": "vessel",
        "net_only_lung": "lung",
        "net_only_airway": "airway"
    }
    return list (map (net_task_dict.get, model_names))


def get_label_list(task_list):
    """
    Get the label list according to given task list.

    :param task_list: a list of task names.
    :return: a list of labels' list.
    """

    task_label_dict = {
        "lobe": [0, 4, 5, 6, 7, 8],
        "vessel": [0, 1],
        "airway": [0, 1],
        "lung": [0, 1],
        "no_label": []
    }

    return list (map (task_label_dict.get, task_list))


def train():
    """
    Main function to train the model.

    :return: None
    """
    # Define the Model
    model_names = ['net_only_vessel']
    if args.aux_output and ('net_only_vessel' in model_names):
        print(model_names)
        raise Exception('net_only_vessel should not have aux output')

    task_list = get_task_list(model_names)
    label_list = get_label_list(task_list)
    path_list = [Mypath(x) for x in task_list] # a list of Mypath objectives

    if args.model_6_levels:
        net_list = cpmodels.load_cp_models_6_levels(model_names,
                                                    nch=1,
                                                    lr=args.lr,
                                                    nf=args.feature_number,
                                                    bn=args.batch_norm,
                                                    dr=args.dropout,
                                                    net_type='v')
    elif args.model_7_levels:
        net_list = cpmodels.load_cp_models_7_levels(model_names,
                                                    nch=1,
                                                    lr=args.lr,
                                                    nf=args.feature_number,
                                                    bn=args.batch_norm,
                                                    dr=args.dropout,
                                                    net_type='v')
    elif args.model_mt_scales:
        net_list = cpmodels.load_cp_models_mt_scales(model_names,
                                                    nch=1,
                                                    lr=args.lr,
                                                    nf=args.feature_number,
                                                    bn=args.batch_norm,
                                                    dr=args.dropout,
                                                    net_type='v')

    else:
        net_list = cpmodels.load_cp_models (model_names,
                                            nch=1,
                                            lr=args.lr,
                                            nf=args.feature_number,
                                            bn=args.batch_norm,
                                            dr=args.dropout,
                                            ds=args.deep_supervision,
                                            aux=args.aux_output,
                                            net_type='v')


    train_data_gen_list = []
    for mypath, task, labels, net, model_name in zip (path_list, task_list, label_list, net_list, model_names):

        plot_model(net, show_shapes=True, to_file=mypath.model_figure_path() + '/' + model_name + '.png')
        print('successfully plot model structure at: ', mypath.model_figure_path() + '/' + model_name + '.png')

        if args.load: # load saved model
            old_time = '1584923362.8464801_0.00011a_o_0.5ds2dr1bn1fs16ptsz144ptzsz64'
            old_model_fpath = mypath.model_path + '/' + task + '/' + old_time + 'MODEL.hdf5'
            net.load_weights(old_model_fpath)
            print('loaded weights successfully: ', old_model_fpath)

        # save model architecture and config
        model_json = net.to_json ()
        with open (mypath.json_fpath(), "w") as json_file:
            json_file.write (model_json)
            print ('successfully write json file of task ', task, mypath.json_fpath())

        if task == 'vessel' or task=='no_label':
            b_extension = '.mhd'
            aux=0
        else:
            b_extension = '.nrrd'
            aux=args.aux_output

        train_it = TwoScanIterator(mypath.train_dir(), task=task,
                                   batch_size=args.batch_size,
                                   sub_dir=mypath.sub_dir(),
                                   trgt_sz=args.trgt_sz, trgt_z_sz=args.trgt_z_sz,
                                   trgt_space=args.trgt_space, trgt_z_space=args.trgt_z_space,
                                   ptch_sz=args.ptch_sz, ptch_z_sz=args.ptch_z_sz,
                                   b_extension=b_extension,
                                   shuffle=False,
                                   patches_per_scan=args.patches_per_scan,
                                   data_argum=True,
                                   ds=args.deep_supervision,
                                   labels=labels,
                                   nb=args.tr_nb,
                                   no_label_dir=args.no_label_dir,
                                   p_middle=args.p_middle,
                                   phase='train',
                                   aux=aux)

        enqueuer_train = GeneratorEnqueuer(train_it.generator(), use_multiprocessing=False)

        train_datas = enqueuer_train.get ()

        enqueuer_train.start ()

        train_data_gen_list.append(train_datas)

    best_tr_loss_dic = {'lobe': 10000,
                     'vessel': 10000,
                     'airway': 10000,
                     'no_label': 10000}
    best_va_loss_dic = {'lobe': 10000,
                     'vessel': 10000,
                     'airway': 10000,
                     'no_label': 10000}

    segment = None # segmentor for prediction every epoch
    training_step = 2500000
    for idx_ in range(training_step):
        print ('step number: ', idx_)
        for task, net, tr_data, va_data, label, mypath in zip(task_list, net_list, train_data_gen_list, valid_data_npy_list, label_list, path_list):


            x, y = next(tr_data) # tr_data is a generator or enquerer
            valid_data = va_data  # va_data is a fixed numpy data

            # callbacks
            train_csvlogger = callbacks.CSVLogger(mypath.train_log_fpath(), separator=',', append=True)
            tr_va_csvlogger = callbacks.CSVLogger(mypath.tr_va_log_fpath(), separator=',', append=True)

            BEST_TR_LOSS = best_tr_loss_dic[task]
            BEST_VA_LOSS = best_va_loss_dic[task]

            class ModelCheckpointWrapper(callbacks.ModelCheckpoint):
                def __init__(self, best_init=None, *arg, **kwagrs):
                    super().__init__(*arg, **kwagrs)
                    if best_init is not None:
                        self.best = best_init

            saver_train = ModelCheckpointWrapper(best_init=BEST_TR_LOSS,
                                                  filepath=mypath.best_tr_loss_location(),
                                                  verbose=1,
                                                  save_best_only=True,
                                                  monitor='loss',
                                                  save_weights_only=True,
                                                  save_freq=1)
            saver_valid = ModelCheckpointWrapper (best_init=BEST_VA_LOSS,
                                                   filepath=mypath.best_va_loss_location(),
                                                   verbose=1,
                                                   save_best_only=True,
                                                   monitor='val_loss',
                                                   save_weights_only=True,
                                                   save_freq=1)

            if idx_ % (500) == 0: # one epoch for lobe segmentation, 20 epochs for vessel segmentation

                history = net.fit (x, y,
                                   batch_size=args.batch_size,
                                   validation_data=valid_data,
                                   use_multiprocessing=True,
                                   callbacks=[saver_valid, tr_va_csvlogger])

                current_val_loss = history.history['val_loss'][0]
                print('val_loss: ', current_val_loss)
                old_val_loss = np.float(best_va_loss_dic[task])
                if current_val_loss<old_val_loss:
                    best_va_loss_dic[task] = current_val_loss

                current_tr_loss = history.history['loss'][0]
                old_tr_loss = np.float(best_tr_loss_dic[task])
                if current_tr_loss < old_tr_loss:
                    best_tr_loss_dic[task] = current_tr_loss

                if task != 'no_label': # save predicted results and compute the dices
                    for phase in ['train', 'valid']:

                        segment = v_seg.v_segmentor(batch_size=args.batch_size,
                                                    model=net,
                                                    ptch_sz = args.ptch_sz, ptch_z_sz = args.ptch_z_sz,
                                                    trgt_sz = args.trgt_sz, trgt_z_sz = args.trgt_z_sz,
                                                    trgt_space_list=[args.trgt_z_space, args.trgt_space, args.trgt_space],
                                                    task=task)

                        write_preds_to_disk(segment=segment,
                                            data_dir = mypath.ori_ct_path( phase),
                                            preds_dir= mypath.pred_path( phase),
                                            number=1, stride = 0.8)

                        write_dices_to_csv (labels=label,
                                            gdth_path=mypath.gdth_path(phase),
                                            pred_path=mypath.pred_path(phase),
                                            csv_file= mypath.dices_fpath(phase))


            else:
                history = net.fit (x, y,
                                   batch_size=args.batch_size,
                                   use_multiprocessing=True,
                                   callbacks=[saver_train, train_csvlogger])

                current_tr_loss = history.history['loss'][0]
                old_tr_loss = np.float(best_tr_loss_dic[task])
                if current_tr_loss < old_tr_loss:
                    best_tr_loss_dic[task] = current_tr_loss

            #print (history.history.keys ())
            for key, result in history.history.items ():
                print(key, result)

    for enqueuer_train in train_data_gen_list:
        enqueuer_train.close () # in the future, close should be replaced by stop

    print('finish train: ', mypath.str_name)


if __name__ == '__main__':
    train()




