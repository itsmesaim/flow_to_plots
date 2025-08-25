import xml.etree.ElementTree as ET
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

XML_FILE = Path("mk-flow.xml")
assert XML_FILE.exists(), f"{XML_FILE} not found. Run your sim first."

root = ET.parse(XML_FILE).getroot()

# ---- Build a classifier map: flowId -> tuple info ----
cls_map = {}  # flowId -> dict(src,dst,proto,srcPort,dstPort)

def absorb_classifier(tag_name):
    cls = root.find(tag_name)
    if cls is None: return
    for f in cls.findall("Flow"):
        fid = int(f.attrib["flowId"])
        cls_map[fid] = {
            "src": f.attrib.get("sourceAddress", ""),
            "dst": f.attrib.get("destinationAddress", ""),
            "proto": int(f.attrib.get("protocol", "0")),
            "srcPort": f.attrib.get("sourcePort", ""),
            "dstPort": f.attrib.get("destinationPort", ""),
        }

absorb_classifier("Ipv4FlowClassifier")
absorb_classifier("FlowClassifier")  # fallback name in some builds

# ---- Iterate stats and join with classifier ----
rows = []
stats_parent = root.find("FlowStats")
if stats_parent is None:
    # some versions nest stats per <Flow> under <FlowMonitor>
    stats_parent = root

for f in stats_parent.findall(".//Flow"):
    fid = int(f.attrib["flowId"])

    txBytes = int(f.attrib.get("txBytes", 0))
    rxBytes = int(f.attrib.get("rxBytes", 0))
    txPackets = int(f.attrib.get("txPackets", 0))
    rxPackets = int(f.attrib.get("rxPackets", 0))
    t_first = float(f.attrib.get("timeFirstTxPacket", 0.0))
    t_last  = float(f.attrib.get("timeLastRxPacket", 0.0))
    delaySum = float(f.attrib.get("delaySum", 0.0))
    jitterSum = float(f.attrib.get("jitterSum", 0.0))

    duration = max(t_last - t_first, 1e-9)
    meanDelay = delaySum / max(rxPackets, 1)
    meanJitter = jitterSum / max(rxPackets - 1, 1)
    lossPkts = max(txPackets - rxPackets, 0)
    lossPct = 100.0 * lossPkts / txPackets if txPackets > 0 else 0.0
    throughput_Mbps = (rxBytes * 8) / duration / 1e6

    c = cls_map.get(fid, {})
    proto_num = c.get("proto", 0)
    proto = {6: "TCP", 17: "UDP"}.get(proto_num, str(proto_num))

    rows.append(dict(
        flowId=fid,
        proto=proto,
        src=f'{c.get("src","")}:{c.get("srcPort","")}',
        dst=f'{c.get("dst","")}:{c.get("dstPort","")}',
        txPackets=txPackets, rxPackets=rxPackets, lossPkts=lossPkts, lossPct=lossPct,
        txBytes=txBytes, rxBytes=rxBytes,
        meanDelay_s=meanDelay, meanJitter_s=meanJitter,
        duration_s=duration, throughput_Mbps=throughput_Mbps
    ))

if not rows:
    raise SystemExit("No flows parsed. Inspect mk-flow.xml structure; did the sim produce flows?")

df = pd.DataFrame(rows).sort_values(["proto","flowId"]).reset_index(drop=True)
csv_path = Path("mk-flow-summary.csv")
df.to_csv(csv_path, index=False)
print(f"Saved: {csv_path.resolve()}")

print("\nTop flows by throughput:")
print(df.sort_values("throughput_Mbps", ascending=False)[
    ["flowId","proto","src","dst","throughput_Mbps"]
].head(10).to_string(index=False))

# ---- Plots ----
plt.figure()
plt.bar(df["flowId"].astype(str), df["throughput_Mbps"])
plt.title("Throughput per flow (Mbps)"); plt.xlabel("Flow ID"); plt.ylabel("Mbps"); plt.tight_layout()
plt.savefig("mk-throughput.png")

plt.figure()
plt.bar(df["flowId"].astype(str), df["lossPct"])
plt.title("Packet loss per flow (%)"); plt.xlabel("Flow ID"); plt.ylabel("Loss %"); plt.tight_layout()
plt.savefig("mk-loss.png")

plt.figure()
plt.bar(df["flowId"].astype(str), [x*1000 for x in df["meanDelay_s"]])
plt.title("Mean one-way delay per flow (ms)"); plt.xlabel("Flow ID"); plt.ylabel("ms"); plt.tight_layout()
plt.savefig("mk-delay.png")

print("Saved plots: mk-throughput.png, mk-loss.png, mk-delay.png")