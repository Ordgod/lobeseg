#!/bin/bash 
#SBATCH --job-name=vessel
##SBATCH --output=output_vessel_only_medium.txt
#SBATCH --ntasks=1 
#SBATCH --cpus-per-task=4

#SBATCH --mem=40G

#SBATCH --partition=gpu-long

##SBATCH --nodelist=node860

#SBATCH --gres=gpu:1
#SBATCH --time=160:00:00 
#SBATCH -e logs/slurm-%j.err
#SBATCH -o logs/slurm-%j.out

echo "on Hostname = $(hostname)"
echo "on GPU      = $CUDA_VISIBLE_DEVICES"
echo
echo "@ $(date)"
echo

eval $(conda shell.bash hook)

conda activate py37
##stdbuf -oL python -u write_preds_save_dice.py
stdbuf -oL python -u train_ori_fit_rec_epoch.py -ds=2 --tr_nb=18  --model_names='net_only_lobe,net_no_label'
##stdbuf -oL python write_preds_save_dice.py
##python plot_curve.py






