# -*- coding: utf-8 -*-
"""
Main file to train the model.
=============================================================
Created on Tue Apr  4 09:35:14 2020
@author: Jingnan

                    .::::.
                  .::::::::.
                 :::::::::::
             ..:::::::::::'
           '::::::::::::'
             .::::::::::
        '::::::::::::::..
             ..::::::::::::.
           ``::::::::::::::::
            ::::``:::::::::'        .:::.
           ::::'   ':::::'       .::::::::.
         .::::'     ::::      .:::::::'::::.
        .:::'       :::::  .:::::::::' ':::::.
       .::'        :::::.:::::::::'      ':::::.
      .::'         ::::::::::::::'         ``::::.
  ...:::           ::::::::::::'              ``::.
 ```` ':.          ':::::::::'                  ::::..

"""

import numpy as np
# import matplotlib.pyplot as plt
from futils.dataloader import ScanIterator
import os
import csv
import gc
import sys
import tensorflow as tf
from tensorflow.keras.utils import GeneratorEnqueuer
from tensorflow.keras import backend as K
from tensorflow.keras import callbacks
from tensorflow.keras.utils import plot_model
from futils import compiled_models as cpmodels
from futils.util import save_model_best

from set_args import args
from write_dice import write_dices_to_csv
from write_batch_preds import write_preds_to_disk
import segmentor as v_seg
from mypath import Mypath
import pyvista as pv
from compute_distance_metrics_and_save import write_all_metrics
from generate_fissure_from_masks import gntFissure




# os.environ['CUDA_VISIBLE_DEVICES'] = "0" # use the first GPU
# tf.keras.mixed_precision.experimental.set_policy('infer')  # mix precision training
os.environ['TF_ENABLE_AUTO_MIXED_PRECISION'] = '1'

config = tf.ConfigProto()
config.gpu_options.allow_growth = True  # dynamically grow the memory used on the GPU
sess = tf.Session(config=config)
K.set_session(sess)  # set this TensorFlow session as the default session for Keras

K.set_learning_phase(1)  # try with 1
print(sys.argv[1:])  # print all arguments passed to script


class Get_list():
    def __init__(self, model_names, current_time=None):
        self.model_names = model_names

    def get_task_list(self):
        """
        Get task list according to a list of model names. Note that one task may corresponds to multiple models.
        :param model_names: a list of model names
        :return: a list of tasks
        """
        net_task_dict = {
            "net_itgt_lb_rc": "lobe",
            "net_itgt_vs_rc": "vessel",
            "net_itgt_lu_rc": "lung",
            "net_itgt_aw_rc": "airway",

            "net_no_label": "no_label",

            "net_only_lobe": "lobe",
            "net_only_vessel": "vessel",
            "net_only_lung": "lung",
            "net_only_airway": "airway"
        }
        return list(map(net_task_dict.get, self.model_names))

    def get_label_list(self):
        """
        Get the label list according to given task list.

        :return: a list of labels' list.
        """

        task_label_dict = {
            "net_itgt_lb_rc": [0, 4, 5, 6, 7, 8],
            "net_itgt_vs_rc": [0, 1],
            "net_itgt_lu_rc": [0, 1],
            "net_itgt_aw_rc": [0, 1],

            "net_no_label": [],

            "net_only_lobe": [0, 4, 5, 6, 7, 8],
            "net_only_vessel": [0, 1],
            "net_only_lung": [0, 1],
            "net_only_airway": [0, 1]
        }

        return list(map(task_label_dict.get, self.model_names))

    def get_path_list(self):
        task_list = self.get_task_list()
        return [Mypath(x) for x in task_list]  # a list of Mypath objectives, each Mypath corresponds to a task

    def get_tr_nb_list(self, myargs):
        tr_nb_dict = {
            "net_itgt_lb_rc": myargs.lb_tr_nb,
            "net_itgt_vs_rc": myargs.vs_tr_nb,
            "net_itgt_lu_rc": myargs.lu_tr_nb,
            "net_itgt_aw_rc": myargs.aw_tr_nb,

            "net_no_label": myargs.rc_tr_nb,

            "net_only_lobe": myargs.lb_tr_nb,
            "net_only_vessel": myargs.vs_tr_nb,
            "net_only_lung": myargs.lu_tr_nb,
            "net_only_airway": myargs.aw_tr_nb
        }

        return list(map(tr_nb_dict.get, self.model_names))

    def get_ao_list(self, myargs):
        ao_dict = {
            "net_itgt_lb_rc": myargs.ao_lb,
            "net_itgt_vs_rc": myargs.ao_vs,
            "net_itgt_lu_rc": myargs.ao_lu,
            "net_itgt_aw_rc": myargs.ao_aw,

            "net_no_label": myargs.ao_rc,

            "net_only_lobe": myargs.ao_lb,
            "net_only_vessel": myargs.ao_vs,
            "net_only_lung": myargs.ao_lu,
            "net_only_airway": myargs.ao_aw
        }
        return list(map(ao_dict.get, self.model_names))

    def get_ds_list(self, myargs):
        ds_dict = {
            "net_itgt_lb_rc": myargs.ds_lb,
            "net_itgt_vs_rc": myargs.ds_vs,
            "net_itgt_lu_rc": myargs.ds_lu,
            "net_itgt_aw_rc": myargs.ds_aw,

            "net_no_label": myargs.ds_rc,

            "net_only_lobe": myargs.ds_lb,
            "net_only_vessel": myargs.ds_vs,
            "net_only_lung": myargs.ds_lu,
            "net_only_airway": myargs.ds_aw
        }
        return list(map(ds_dict.get, self.model_names))

    def get_tsp_list(self, myargs):
        tsp_dict = {  # lstrip() is necessary because the pycharm always reformat my code.
            "net_itgt_lb_rc": [float(i.lstrip()) for i in myargs.tsp_lb.split('_')],
            "net_itgt_vs_rc": [float(i.lstrip()) for i in myargs.tsp_vs.split('_')],
            "net_itgt_lu_rc": [float(i.lstrip()) for i in myargs.tsp_lu.split('_')],
            "net_itgt_aw_rc": [float(i.lstrip()) for i in myargs.tsp_aw.split('_')],

            "net_no_label": [float(i.lstrip()) for i in myargs.tsp_rc.split('_')],

            "net_only_lobe": [float(i.lstrip()) for i in myargs.tsp_lb.split('_')],
            "net_only_vessel": [float(i.lstrip()) for i in myargs.tsp_vs.split('_')],
            "net_only_lung": [float(i.lstrip()) for i in myargs.tsp_lu.split('_')],
            "net_only_airway": [float(i.lstrip()) for i in myargs.tsp_aw.split('_')]
        }

        return list(map(tsp_dict.get, self.model_names))

    def get_low_msk_list(self, myargs):
        low_msk_dict = {
            "net_itgt_lb_rc": myargs.low_msk_lb,
            "net_itgt_vs_rc": myargs.low_msk_vs,
            "net_itgt_lu_rc": myargs.low_msk_lu,
            "net_itgt_aw_rc": myargs.low_msk_aw,

            "net_no_label": myargs.low_msk_rc,

            "net_only_lobe": myargs.low_msk_lb,
            "net_only_vessel": myargs.low_msk_vs,
            "net_only_lung": myargs.low_msk_lu,
            "net_only_airway": myargs.low_msk_aw
        }
        return list(map(low_msk_dict.get, self.model_names))

    def get_mot_list(self, myargs):
        mot_dict = {
            "net_itgt_lb_rc": myargs.mot_lb,
            "net_itgt_vs_rc": myargs.mot_vs,
            "net_itgt_lu_rc": myargs.mot_lu,
            "net_itgt_aw_rc": myargs.mot_aw,

            "net_no_label": myargs.mot_rc,

            "net_only_lobe": myargs.mot_lb,
            "net_only_vessel": myargs.mot_vs,
            "net_only_lung": myargs.mot_lu,
            "net_only_airway": myargs.mot_aw
        }
        return list(map(mot_dict.get, self.model_names))

    def get_load_name_list(self, myargs):
        load_name_dict = {
            "net_itgt_lb_rc": myargs.ld_itgt_lb_rc_name,
            "net_itgt_vs_rc": myargs.ld_itgt_vs_rc_name,
            "net_itgt_lu_rc": myargs.ld_itgt_lu_rc_name,
            "net_itgt_aw_rc": myargs.ld_itgt_aw_rc_name,

            "net_no_label": myargs.ld_rc_name,

            "net_only_lobe": myargs.ld_lb_name,
            "net_only_vessel": myargs.ld_vs_name,
            "net_only_lung": myargs.ld_lu_name,
            "net_only_airway": myargs.ld_aw_name
        }

        return list(map(load_name_dict.get, self.model_names))

def get_zip_list(model_names, args):
    gl = Get_list(model_names)
    task_list = gl.get_task_list()  # for example, 6 model_names corresponds to 6 tasks
    label_list = gl.get_label_list()  # for example, 6 model_names corresponds to 6 labels
    path_list = gl.get_path_list()
    load_name_list = gl.get_load_name_list(args)
    tr_nb_list = gl.get_tr_nb_list(args)
    ao_list = gl.get_ao_list(args)
    ds_list = gl.get_ds_list(args)
    mot_list = gl.get_mot_list(args)
    tsp_list = gl.get_tsp_list(args)
    low_msk_list = gl.get_low_msk_list(args)

    net_list = cpmodels.load_cp_models(model_names, args)

    return net_list, path_list, task_list, label_list, model_names, load_name_list,\
           tr_nb_list, ao_list, ds_list, mot_list, tsp_list, low_msk_list


def get_monitor_data(mot, valid_datas, task, ao, ds, monitor_nb=10):
    if mot:
        valid_data_y_numpy1, valid_data_y_numpy2 = [], []
        valid_data_x_numpy1, valid_data_x_numpy2 = [], []
        for i in range(monitor_nb):  # use 10 valid patches to save best valid model
            one_valid_data = next(valid_datas)  # cost 7 seconds per image patch using val_it.generator()
            one_valid_data_x, one_valid_data_y = one_valid_data  # output shape:(1,144,144,80,1) or a list with two arrays
            valid_data_x_numpy1.append(one_valid_data_x[0][0])
            valid_data_x_numpy2.append(one_valid_data_x[1][0])
            valid_data_y_numpy1.append(one_valid_data_y[0][0])
            valid_data_y_numpy2.append(one_valid_data_y[1][0])
        valid_data_numpy = [[np.array(valid_data_x_numpy1), np.array(valid_data_x_numpy2)],
                            [np.array(valid_data_y_numpy1), np.array(valid_data_y_numpy2)]]
    else:
        if task == 'no_label':
            valid_data_x_numpy = []
            valid_data_x_numpy1, valid_data_x_numpy2 = [], []
            valid_data_y_numpy = []

            for i in range(monitor_nb):
                one_valid_data = next(valid_datas)  # cost 7 seconds per image patch using val_it.generator() [x, y]
                one_valid_data_x = one_valid_data[0]  # output shape:(1,144,144,80,1)
                if type(one_valid_data_x) is np.ndarray:
                    valid_data_x_numpy.append(one_valid_data_x[0])  # output shape:(144,144,80,1)
                else:
                    valid_data_x_numpy1.append(one_valid_data_x[0][0])  # output shape:(144,144,80,1)
                    valid_data_x_numpy2.append(one_valid_data_x[1][0])  # output shape:(144,144,80,1)

                one_valid_data_y = one_valid_data[1]  # output shape:(1,144,144,80,1)
                valid_data_y_numpy.append(one_valid_data_y[0][0])

            if len(valid_data_x_numpy):
                valid_data_numpy = [np.array(valid_data_x_numpy), np.array(valid_data_y_numpy)]
            else:
                valid_data_numpy = [[np.array(valid_data_x_numpy1), np.array(valid_data_x_numpy2)], np.array(valid_data_y_numpy)]
        else:
            if ao and ds == 2:
                out_nb = 4
                valid_data_y_numpy = [[], [], [], []]
            elif ao and ds == 0:
                out_nb = 2
                valid_data_y_numpy = [[], []]
            elif ao == False and ds == 2:
                out_nb = 3
                valid_data_y_numpy = [[], [], []]
            elif ao == False and ds == 0:
                out_nb = 1
                valid_data_y_numpy = [[]]
            else:
                raise Exception('Please set the correct aux and ds!!!')

            valid_data_x_numpy = []
            valid_data_x_numpy1, valid_data_x_numpy2 = [], []
            for i in range(10):  # use 10 valid patches to save best valid model
                one_valid_data = next(valid_datas)  # cost 7 seconds per image patch using val_it.generator()
                one_valid_data_x = one_valid_data[0]  # output shape:(1,144,144,80,1) or a list with two arrays
                if type(one_valid_data_x) is np.ndarray:
                    valid_data_x_numpy.append(one_valid_data_x[0])
                else:
                    valid_data_x_numpy1.append(one_valid_data_x[0][0])
                    valid_data_x_numpy2.append(one_valid_data_x[1][0])

                one_valid_data_y = one_valid_data[1]  # output 4 lists, each list has shape:(1,144,144,80,1)
                for j in range(out_nb):
                    valid_data_y_numpy[j].append(one_valid_data_y[j][0])
            for _ in range(out_nb):
                valid_data_y_numpy[_] = np.asarray(valid_data_y_numpy[_])
            if len(valid_data_x_numpy):
                valid_data_numpy = [np.array(valid_data_x_numpy), valid_data_y_numpy]
            else:
                valid_data_numpy = [[np.array(valid_data_x_numpy1), np.array(valid_data_x_numpy2)], valid_data_y_numpy]
    return valid_data_numpy

def get_dict():
    best_tr_loss_dict = {
        "net_itgt_lb_rc": 10000,
        "net_itgt_vs_rc": 10000,
        "net_itgt_lu_rc": 10000,
        "net_itgt_aw_rc": 10000,

        "net_no_label": 10000,

        "net_only_lobe": 10000,
        "net_only_vessel": 10000,
        "net_only_lung": 10000,
        "net_only_airway": 10000
    }
    best_vd_loss_dict = {
        "net_itgt_lb_rc": 10000,
        "net_itgt_vs_rc": 10000,
        "net_itgt_lu_rc": 10000,
        "net_itgt_aw_rc": 10000,

        "net_no_label": 10000,

        "net_only_lobe": 10000,
        "net_only_vessel": 10000,
        "net_only_lung": 10000,
        "net_only_airway": 10000
    }
    lr_dict = {"net_itgt_lb_rc": 0.0001,
               "net_itgt_vs_rc": 0.0001,
               "net_itgt_lu_rc": 0.0001,
               "net_itgt_aw_rc": 0.0001,

               "net_no_label": 0.0001,

               "net_only_lobe": 0.0001,
               "net_only_vessel": 0.0001,
               "net_only_lung": 0.0001,
               "net_only_airway": 0.0001}
    current_tr_loss_dict = {
        "net_itgt_lb_rc": 10000,
        "net_itgt_vs_rc": 10000,
        "net_itgt_lu_rc": 10000,
        "net_itgt_aw_rc": 10000,

        "net_no_label": 10000,

        "net_only_lobe": 10000,
        "net_only_vessel": 10000,
        "net_only_lung": 10000,
        "net_only_airway": 10000
    }

    return best_tr_loss_dict, best_vd_loss_dict, current_tr_loss_dict, lr_dict


def get_attentioned_y(y, lobe_pred):
    while type(y) is list:  # multi outputs
        y = y[0]

    if y.shape[-1] == 2:  # 2 channels, for vessel or airway or other binary segmentation task
        monitor_y_tmp = y[..., 1][..., np.newaxis]
    elif y.shape[-1] == 1:  # 1 channel, reconstruction task
        monitor_y_tmp = y
    else:
        raise Exception('ground truth has a channel number: ', str(y.shape[-1]), ' which should be 1 or 2:')

    return monitor_y_tmp * lobe_pred

def train():
    """
    Main function to train the model.
    :return: None
    """
    # Define the Model, use dash to separate multi model names, do not use ',' to separate it,
    #  because ',' can lead to unknown error during parse arguments
    model_names = args.model_names.split('-')
    model_names = [i.lstrip() for i in model_names]  # remove backspace before each model name
    print('model names: ', model_names)

    train_data_gen_list = []
    valid_array_list = []
    net_list, path_list, task_list, label_list, model_names, load_name_list,\
    tr_nb_list, ao_list, ds_list, mot_list, tsp_list, low_msk_list = get_zip_list(model_names, args)

    zip_list = zip(net_list, path_list, task_list, label_list, model_names, load_name_list,\
    tr_nb_list, ao_list, ds_list, mot_list, tsp_list, low_msk_list)

    net_trained_lobe = None

    for net, mypath, task, labels, model_name, ld_name, tr_nb, ao, ds, mot, tsp, low_msk in zip_list:
        model_figure_fpath = mypath.model_figure_path() + '/' + model_name + '.png'
        plot_model(net, show_shapes=True, to_file=model_figure_fpath)
        print('successfully plot model structure at: ', model_figure_fpath)
        if ld_name is not 'None':  # 'None' is from arg parse as string
            saved_model = mypath.best_model_fpath(phase='valid', str_name=ld_name, task=task)
            net.load_weights(saved_model)
            print('loaded lobe weights successfully from: ', saved_model)

        # save model architecture and config
        model_json = net.to_json()
        with open(mypath.json_fpath(), "w") as json_file:
            json_file.write(model_json)
            print('successfully write new json file of task ', task, mypath.json_fpath())

        train_it = ScanIterator(mypath.data_dir('train'), task=task,
                                sub_dir=mypath.sub_dir(),
                                ptch_sz=args.ptch_sz, ptch_z_sz=args.ptch_z_sz,
                                trgt_sz=args.trgt_sz, trgt_z_sz=args.trgt_z_sz,
                                trgt_space=tsp[0], trgt_z_space=tsp[1],
                                data_argum=True,
                                patches_per_scan=args.patches_per_scan,
                                ds=ds,
                                labels=labels,
                                batch_size=args.batch_size,
                                shuffle=True,
                                n=tr_nb,
                                no_label_dir=args.no_label_dir,
                                p_middle=args.p_middle,
                                aux=ao,
                                mtscale=args.mtscale,
                                ptch_seed=None,
                                mot=mot,
                                low_msk=low_msk)

        valid_it = ScanIterator(mypath.data_dir('monitor'), task=task,
                                sub_dir=mypath.sub_dir(),
                                ptch_sz=args.ptch_sz, ptch_z_sz=args.ptch_z_sz,
                                trgt_sz=args.trgt_sz, trgt_z_sz=args.trgt_z_sz,
                                trgt_space=tsp[0], trgt_z_space=tsp[1],
                                data_argum=False,
                                patches_per_scan=args.patches_per_scan,
                                ds=ds,
                                labels=labels,
                                batch_size=args.batch_size,
                                shuffle=False,
                                n=1,  # only use one data
                                no_label_dir=args.no_label_dir,
                                p_middle=args.p_middle,
                                aux=ao,
                                mtscale=args.mtscale,
                                ptch_seed=1,
                                mot=mot,
                                low_msk=low_msk)

        train_datas = train_it.generator(workers=5, qsize=4)
        valid_datas = valid_it.generator(workers=1, qsize=1)

        train_data_gen_list.append(train_datas)
        valid_data_numpy = get_monitor_data(monitor_nb=10, mot=mot, valid_datas=valid_datas, task=task, ao=ao, ds=ds)
        if args.attention and task!='lobe':
            if net_trained_lobe is None:
                if args.mtscale:
                    trained_lobe_name = "1599479049_59_lrlb0.0001lrvs1e-05mtscale1netnolpm0.5nldLUNA16ao1ds2tsp1.4z2.5pps100lbnb17vsnb50nlnb400ptsz144ptzsz96"
                else:
                    trained_lobe_name = "1599479049_663_lrlb0.0001lrvs1e-05mtscale0netnolpm0.5nldLUNA16ao1ds2tsp1.4z2.5pps100lbnb17vsnb50nlnb400ptsz144ptzsz96"
                trained_lobe_fpath = "/data/jjia/new/models/lobe/" + trained_lobe_name + "_valid.hdf5"
                # net_trained_lobe.load_weights(trained_lobe_fpath)
                graph1 = tf.Graph()
                with graph1.as_default():
                    session1 = tf.Session()
                    with session1.as_default():
                        net_trained_lobe = tf.keras.models.load_model(trained_lobe_fpath)
                print('generate validation data by loading trained lobe weights successfully from: ', trained_lobe_fpath)

            with graph1.as_default():
                with session1.as_default():
                    lobe_pred = net_trained_lobe.predict(valid_data_numpy[0], batch_size=1)
                    while type(lobe_pred) is list: # multi outputs
                        lobe_pred = lobe_pred[0]

            valid_data_numpy[1] = get_attentioned_y(valid_data_numpy[1], lobe_pred)

        valid_array_list.append(valid_data_numpy)

    del net_trained_lobe
    gc.collect()

    best_tr_loss_dict, best_vd_loss_dict, current_tr_loss_dict, lr_dict = get_dict()
    for idx_ in range(args.step_nb):
        print('step number: ', idx_)
        zip_list2 = zip(task_list, net_list, train_data_gen_list, label_list, path_list, model_names, valid_array_list,
                        tsp_list)

        for net, task in zip(net_list, task_list):
            if task == 'lobe':
                net_lobe = net

        for task, net, tr_data, label, mypath, model_name, valid_array, tsp in zip_list2:
            if len(net_list) == 3:
                if (idx_ % 2 == 0) and task == "lobe":
                    continue
                elif (idx_ % 2 == 1) and task == "vessel":
                    continue

            if task != "lobe":
                if args.adaptive_lr:
                    loss_ratio = current_tr_loss_dict["net_only_lobe"] / current_tr_loss_dict[model_name]
                    print('loss_ratio: ', loss_ratio, file=sys.stderr)
                    print('step number', idx_, 'old lr for', task, 'is', K.eval(net.optimizer.lr), file=sys.stderr)
                    new_lr = loss_ratio * args.lr_lb * 0.1
                    K.set_value(net.optimizer.lr, new_lr)
                print('step number', idx_, ' lr for', task, 'is', K.eval(net.optimizer.lr), file=sys.stderr)

            x, y = next(tr_data)  # tr_data is a generator or enquerer
            # callbacks
            train_csvlogger = callbacks.CSVLogger(mypath.log_fpath('train'), separator=',', append=True)
            valid_csvlogger = callbacks.CSVLogger(mypath.log_fpath('valid'), separator=',', append=True)
            BEST_TR_LOSS = best_tr_loss_dict[model_name]  # set this value to record the best tr_loss for each task,
            BEST_VD_LOSS = best_vd_loss_dict[model_name]

            class ModelCheckpointWrapper(callbacks.ModelCheckpoint):
                def __init__(self, best_init=None, *arg, **kwagrs):
                    super().__init__(*arg, **kwagrs)
                    if best_init is not None:
                        self.best = best_init

            saver_train = ModelCheckpointWrapper(best_init=BEST_TR_LOSS,
                                                 filepath=mypath.model_fpath_best_patch('train'),
                                                 verbose=1,
                                                 save_best_only=True,
                                                 monitor='loss',  # do not add valid_data here, save time!
                                                 save_weights_only=True)

            saver_valid = ModelCheckpointWrapper(best_init=BEST_VD_LOSS,
                                                 filepath=mypath.model_fpath_best_patch('valid'),
                                                 verbose=1,
                                                 save_best_only=True,
                                                 monitor='val_loss',  # do not add valid_data here, save time!
                                                 save_weights_only=True)

            small_period_valid = 100
            if args.attention and task!='lobe':
                lobe_pred = net_lobe.predict(x)
                if type(lobe_pred) is list:  # multi outputs
                    lobe_pred = lobe_pred[0]
                y = get_attentioned_y(y, lobe_pred)

            if idx_ % small_period_valid == 0:  # every 100 steps, valid once, save time, keep best valid model
                # print(x.shape, y.shape)
                history = net.fit(x, y, batch_size=args.batch_size, validation_data=tuple(valid_array),
                                  callbacks=[saver_train, saver_valid, train_csvlogger, valid_csvlogger])
                current_vd_loss = history.history['val_loss'][0]
                old_vd_loss = np.float(best_vd_loss_dict[model_name])
                if current_vd_loss < old_vd_loss:
                    best_vd_loss_dict[model_name] = current_vd_loss
            else:
                history = net.fit(x, y, batch_size=args.batch_size, callbacks=[saver_train, train_csvlogger])

            for key, result in history.history.items():
                print(key, result)

            current_tr_loss = history.history['loss'][0]
            old_tr_loss = np.float(best_tr_loss_dict[model_name])
            if current_tr_loss < old_tr_loss:
                best_tr_loss_dict[model_name] = current_tr_loss
            current_tr_loss_dict[model_name] = current_tr_loss

            period_valid = 5000  # every 5000 step, predict a whole ct scan from training and valid dataset
            if (idx_ % (period_valid) == 0) and (task == 'lobe'):
                # In my multi-task model (co-training, or alternative training), I can not use validation_data and
                # validation_freq in net.fit() function. Because there are only one step (patch) at each fit().
                # So in order to assess the valid metrics, I use an independent function to predict the validation
                # and training dataset. And I can also set the period_valid as the validation_freq.
                # save predicted results and compute the dices
                for phase in ['valid']:
                    segment = v_seg.v_segmentor(batch_size=args.batch_size,
                                                model=mypath.model_fpath_best_patch(phase),
                                                ptch_sz=args.ptch_sz, ptch_z_sz=args.ptch_z_sz,
                                                trgt_sz=args.trgt_sz, trgt_z_sz=args.trgt_z_sz,
                                                trgt_space_list=[tsp[1], tsp[0], tsp[0]],
                                                task=task, low_msk=low_msk, attention=args.attention)

                    if idx_ == args.step_nb - 1:  # last step
                        test_nb = 5
                        stride = 0.25
                    else:
                        test_nb = 1
                        stride = 0.8

                    write_preds_to_disk(segment=segment,
                                        data_dir=mypath.ori_ct_path(phase),
                                        preds_dir=mypath.pred_path(phase),
                                        number=test_nb, stride=stride)  # set stride 0.8 to save time

                    if idx_ == args.step_nb - 1:
                        gntFissure(mypath.pred_path(phase), radiusValue=3)
                        for fissure in [False, True]:  # write metrics for lobe and fissure
                            write_all_metrics(labels=labels[1:],  # exclude background
                                              gdth_path=mypath.gdth_path(phase),
                                              pred_path=mypath.pred_path(phase),
                                              csv_file=mypath.all_metrics_fpath(phase, fissure=fissure),
                                              fissure=fissure)
                    else:
                        write_dices_to_csv(step_nb=idx_,
                                           labels=label,
                                           gdth_path=mypath.gdth_path(phase),
                                           pred_path=mypath.pred_path(phase),
                                           csv_file=mypath.dices_fpath(phase))

                    save_model_best(dice_file=mypath.dices_fpath(phase),
                                    segment=segment,
                                    model_fpath=mypath.best_model_fpath(phase))

                    print('step number', idx_, 'lr for', task, 'is', K.eval(net.optimizer.lr), file=sys.stderr)

    print('finish train: ', mypath.str_name)

if __name__ == '__main__':
    train()
