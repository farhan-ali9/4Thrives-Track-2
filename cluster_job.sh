#!/bin/bash
#
# Leonardo HPC cluster — UNIQA Conversion Coach simulation
# User:    a08trc04
# Account: euhpc_d30_031  (EuroHPC project allocation — has active budget)
#
# How to use:
#   1. SSH into Leonardo:  ssh a08trc04@login.leonardo.cineca.it
#   2. Upload project:     scp -r . a08trc04@login.leonardo.cineca.it:~/4Thrives-Track-2/
#   3. Submit job:         sbatch cluster_job.sh
#   4. Monitor:            squeue -u a08trc04
#   5. Results:            ls coach_sim/results/cluster/
#
#SBATCH --job-name=uniqa-coach-sim
#SBATCH --account=euhpc_d30_031
#SBATCH --partition=boost_usr_prod
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=1
#SBATCH --time=00:30:00
#SBATCH --output=logs/cluster_%j.out
#SBATCH --error=logs/cluster_%j.err
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --mail-user=farhanghulam09876@gmail.com

# Environment setup
module load python/3.11
source venv/bin/activate   # or: conda activate your_env

cd $SLURM_SUBMIT_DIR
mkdir -p logs coach_sim/results/cluster

echo "=============================="
echo "Job $SLURM_JOB_ID | User: a08trc04"
echo "Node: $(hostname) | Cores: $SLURM_NTASKS"
echo "Runs per persona: 10000 | Workers: 8"
echo "=============================="

# Run simulation
python -m coach_sim.run_cluster \
    --runs 10000 \
    --workers 8 \
    --out coach_sim/results/cluster \
    --seed 42

echo "Job $SLURM_JOB_ID finished — results in coach_sim/results/cluster"
