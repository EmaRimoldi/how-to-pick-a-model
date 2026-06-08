#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/home/erimoldi/openclaw_remote/projects/NeurIPS_2026}"
cd "${REPO_ROOT}"

RUN_ID="${RUN_ID:-codex_suite_100_vs_gpt55_$(date +%Y%m%d_%H%M%S)}"
STUDY_ROOT="${STUDY_ROOT:-swebench/studies/codex_suite_100_vs_gpt55}"
STUDY_ROOT="${STUDY_ROOT%/}"
SLURM_DIR="${SLURM_DIR:-${STUDY_ROOT}/slurm}"
mkdir -p "${SLURM_DIR}" "${STUDY_ROOT}/runs" "${STUDY_ROOT}/evaluations"

SCRIPT_PATH="${SLURM_DIR}/${RUN_ID}.slurm"
cat > "${SCRIPT_PATH}" <<EOF
#!/usr/bin/env bash
#SBATCH --job-name=${RUN_ID}
#SBATCH --partition=${PARTITION:-mit_preemptable}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=${CPUS_PER_TASK:-4}
#SBATCH --mem=${MEM:-32G}
#SBATCH --time=${TIME_LIMIT:-2-00:00:00}
#SBATCH --output=${SLURM_DIR}/%x-%j.out
#SBATCH --error=${SLURM_DIR}/%x-%j.err

set -euo pipefail

export REPO_ROOT=${REPO_ROOT}
export RUN_ID=${RUN_ID}
export STUDY_ROOT=${STUDY_ROOT}
export MAX_INSTANCES=${MAX_INSTANCES:-100}
export PARALLEL_WORKERS=${PARALLEL_WORKERS:-1}
export MAX_CALLS_PER_COMPONENT=${MAX_CALLS_PER_COMPONENT:-1}
export VERIFY_TIMEOUT=${VERIFY_TIMEOUT:-1800}
export PATH="\${HOME}/.nvm/versions/node/v24.14.1/bin:\${PATH}"

cd "${REPO_ROOT}"
echo "slurm_job_id=\${SLURM_JOB_ID:-none}"
echo "host=\$(hostname)"
echo "date=\$(date -Is)"
bash swebench/scripts/run_codex_suite_100_vs_gpt55.sh
EOF

chmod 700 "${SCRIPT_PATH}"
sbatch "${SCRIPT_PATH}"
echo "slurm_script=${SCRIPT_PATH}"
