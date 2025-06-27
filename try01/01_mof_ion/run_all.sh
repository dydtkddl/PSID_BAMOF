BASE_DIR="/home/ys/PSID_BAMOF/01_mof_ion/"

# Nodes and corresponding job directories
nodes=(psid07 psid08 psid09 psid10)


# Nodes and corresponding job directories
nodes=(psid07 psid08 psid09 psid10)
dirs=("BAMOF_TFS" "BAMOF_BMI" "MIL125_BMI" "MIL125_TFS")

# Dispatch jobs in parallel
for idx in "${!nodes[@]}"; do
  node="${nodes[$idx]}"
  dir="${dirs[$idx]}"
  echo "Starting job on ${node} in ${BASE_DIR}/${dir}/try02"
  # Use -n to prevent reading from stdin, background ssh locally
  ssh -n "${node}" \
    "cd ${BASE_DIR}/${dir}/try02 && nohup mpirun -np 32 pw.x < input.in > input.out 2>&1 &" &
done

# Wait for all ssh dispatches to complete
wait

echo "All jobs dispatched to nodes: ${nodes[*]}"

