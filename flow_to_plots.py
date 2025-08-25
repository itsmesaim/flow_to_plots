import xml.etree.ElementTree as ET
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

XML_FILE = Path("mk-flow.xml")
assert XML_FILE.exists(), f"{XML_FILE} not found. Run your sim first."

# --- Parse FlowMonitor XML ---
tree = ET.parse(XML_FILE)
root = tree.getroot()

rows = []
for flow in root.iter("Flow"):
    fid = int(flow.attrib["flowId"])
    # ipv4 = flow.find("Ipv4FlowClassifier")
    # five_tuple = ipv4.find("Flow")
    ipv4 = flow.find("Ipv4FlowClassifier")
    if ipv4 is None:
        ipv4 = flow.find("FlowClassifier")   # fallback for your ns-3 version
    if ipv4 is not None:
        five_tuple = ipv4.find("Flow")
    else:
        continue  # skip if no classifier found

    # 5-tuple info
    src = five_tuple.attrib.get("sourceAddress", "")
    dst = five_tuple.attrib.get("destinationAddress", "")
    proto = int(five_tuple.attrib.get("protocol", "0"))
    srcPort = five_tuple.attrib.get("sourcePort", "")
    dstPort = five_tuple.attrib.get("destinationPort", "")

    stats = flow.find("FlowStats")
    txBytes = int(stats.attrib.get("txBytes", 0))
    rxBytes = int(stats.attrib.get("rxBytes", 0))
    txPackets = int(stats.attrib.get("txPackets", 0))
    rxPackets = int(stats.attrib.get("rxPackets", 0))
    timeFirstTx = float(stats.attrib.get("timeFirstTxPacket", 0.0))
    timeLastRx  = float(stats.attrib.get("timeLastRxPacket", 0.0))
    meanDelay   = float(stats.attrib.get("delaySum", 0.0)) / max(rxPackets,1)
    meanJitter  = float(stats.attrib.get("jitterSum", 0.0)) / max(rxPackets-1,1)

    duration = max(timeLastRx - timeFirstTx, 1e-9)  # seconds
    throughput_mbps = (rxBytes * 8) / duration / 1e6
    loss_pkts = max(txPackets - rxPackets, 0)
    loss_pct = 100.0 * loss_pkts / txPackets if txPackets > 0 else 0.0

    proto_name = {6:"TCP", 17:"UDP"}.get(proto, str(proto))

    rows.append(dict(
        flowId=fid, proto=proto_name,
        src=f"{src}:{srcPort}", dst=f"{dst}:{dstPort}",
        txPackets=txPackets, rxPackets=rxPackets, lossPkts=loss_pkts, lossPct=loss_pct,
        txBytes=txBytes, rxBytes=rxBytes,
        meanDelay_s=meanDelay, meanJitter_s=meanJitter,
        duration_s=duration, throughput_Mbps=throughput_mbps
    ))

df = pd.DataFrame(rows).sort_values(["proto","flowId"]).reset_index(drop=True)

# Save CSV
csv_path = Path("mk-flow-summary.csv")
df.to_csv(csv_path, index=False)
print(f"Saved: {csv_path.resolve()}")

# Print a small summary to console
print("\nTop flows by throughput:")
print(df.sort_values("throughput_Mbps", ascending=False)[["flowId","proto","src","dst","throughput_Mbps"]].head(10).to_string(index=False))

# --- Plots ---
# 1) Throughput per flow
plt.figure()
plt.bar(df["flowId"].astype(str), df["throughput_Mbps"])
plt.title("Throughput per flow (Mbps)")
plt.xlabel("Flow ID")
plt.ylabel("Mbps")
plt.tight_layout()
plt.savefig("mk-throughput.png")

# 2) Packet loss % per flow
plt.figure()
plt.bar(df["flowId"].astype(str), df["lossPct"])
plt.title("Packet loss per flow (%)")
plt.xlabel("Flow ID")
plt.ylabel("Loss %")
plt.tight_layout()
plt.savefig("mk-loss.png")

# 3) Mean delay per flow
plt.figure()
plt.bar(df["flowId"].astype(str), [d*1000 for d in df["meanDelay_s"]])
plt.title("Mean one-way delay per flow (ms)")
plt.xlabel("Flow ID")
plt.ylabel("ms")
plt.tight_layout()
plt.savefig("mk-delay.png")

print("Saved plots: mk-throughput.png, mk-loss.png, mk-delay.png")