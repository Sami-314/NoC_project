import os
import subprocess
import matplotlib.pyplot as plt

base_dir = os.path.dirname(os.path.abspath(__file__))
booksim_dir = os.path.dirname(base_dir)
runfile_dir = os.path.join(booksim_dir, "runfiles")
result_dir = os.path.join(booksim_dir, "results")
os.makedirs(result_dir, exist_ok=True)

booksim_exe = os.path.join(booksim_dir, "src", "booksim")

# Sweep
k_values = [3, 4, 5, 6, 7]
injection_rates = [0.05, 0.1, 0.15]
packet_sizes = [4, 12]

results = []

for k in k_values:
    for inj_rate in injection_rates:
        for pkt_size in packet_sizes:
            cfg_name = f"mesh_k{k}_inj{inj_rate}_pkt{pkt_size}.cfg"
            cfg_path = os.path.join(runfile_dir, cfg_name)

            with open(cfg_path, "w") as f:
                f.write(f"""\
topology = mesh;
k = {k};
n = 2;
routing_function = dor;
traffic = uniform;
packet_size = {pkt_size};
injection_rate = {inj_rate};
sim_count = 100000;
warmup_periods = 1000;
""")

            result_path = os.path.join(result_dir, f"{cfg_name}.out")
            with open(result_path, "w") as out_file:
                subprocess.run([booksim_exe, cfg_path], stdout=out_file)

            avg_latency = None
            with open(result_path, "r") as f:
                for line in f:
                    if "Packet latency average" in line:
                        parts = line.strip().split('=')
                        if len(parts) > 1:
                            try:
                                avg_latency = float(parts[1].strip())
                            except:
                                pass

            if avg_latency is not None:
                results.append({
                    "k": k,
                    "injection_rate": inj_rate,
                    "packet_size": pkt_size,
                    "avg_latency": avg_latency
                })

# packet_size별로 plot
for pkt_size in packet_sizes:
    plt.figure()
    for k in k_values:
        subset = [r for r in results if r['k'] == k and r['packet_size'] == pkt_size]
        rates = [r['injection_rate'] for r in subset]
        latencies = [r['avg_latency'] for r in subset]
        plt.plot(rates, latencies, marker='o', label=f'k={k}')

    plt.xlabel('Injection Rate')
    plt.ylabel('Average Packet Latency')
    plt.title(f'Latency vs Injection Rate (Packet Size={pkt_size})')
    plt.legend()
    plt.grid(True)

plt.show()
