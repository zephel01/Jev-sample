import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams["font.family"] = "Noto Sans CJK JP"
plt.rcParams["axes.unicode_minus"] = False

SURF = "#fcfcfb"; INK = "#0b0b0b"; INK2 = "#52514e"
BLUE = "#2a78d6"; ORANGE = "#eb6834"; AQUA = "#1baf7a"; GRAY = "#a8a7a1"
OUT = "./"


def frame(ax, xgrid=False, ygrid=False):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#d9d8d3")
    ax.tick_params(axis="y", length=0, labelcolor=INK)
    ax.tick_params(axis="x", color="#d9d8d3", labelcolor=INK)
    if xgrid:
        ax.xaxis.grid(True, color="#e6e5e0", linewidth=1, zorder=0)
    if ygrid:
        ax.yaxis.grid(True, color="#e6e5e0", linewidth=1, zorder=0)
    ax.set_axisbelow(True)


# ---------- 図4: 4条件での正解率 ----------
fig, ax = plt.subplots(figsize=(6.8, 3.9), dpi=200)
fig.patch.set_facecolor(SURF); ax.set_facecolor(SURF)
conds = ["日本語\n雑談なし", "日本語\n雑談あり", "英語\n雑談なし", "英語\n雑談あり"]
direct = [48.3, 55.0, 56.7, 65.0]
decomp = [98.3, 86.7, 99.2, 96.7]
x = np.arange(4); w = 0.34
b1 = ax.bar(x - w/2 - 0.012, direct, w, color=ORANGE, zorder=3, label="4択を1回で聞く")
b2 = ax.bar(x + w/2 + 0.012, decomp, w, color=BLUE, zorder=3, label="前提条件4問に割って合成")
for bars in (b1, b2):
    for b in bars:
        ax.text(b.get_x() + b.get_width()/2, b.get_height() + 1.8, f"{b.get_height():.1f}",
                ha="center", fontsize=10, color=INK, weight="bold")
ax.set_xticks(x); ax.set_xticklabels(conds, fontsize=10)
ax.set_ylim(0, 112); ax.set_yticks([0, 25, 50, 75, 100])
ax.set_yticklabels(["0", "25", "50", "75", "100%"], fontsize=9, color=INK2)
frame(ax, ygrid=True)
ax.legend(frameon=False, fontsize=9.5, loc="upper left", bbox_to_anchor=(0, 1.02), ncol=2)
ax.set_title("同じモデル・同じ情報量で、聞き方だけを変えた正解率",
             fontsize=13, color=INK, weight="bold", loc="left", pad=44)
ax.text(0, 1.10, "Claude Code のハーネス選択 120シナリオ（各ラベル30件の均衡設計）を自分で実行。2026-09-18、jev-1.13.0",
        fontsize=8.8, color=INK2, transform=ax.transAxes)
fig.savefig(OUT + "2026-09-18_Jev使い方_図4_聞き方だけで正解率が50ポイント動いた.png",
            facecolor=SURF, bbox_inches="tight", pad_inches=0.18)
plt.close(fig)

# ---------- 図5: 個別条件は読めている ----------
fig, ax = plt.subplots(figsize=(6.8, 4.2), dpi=200)
fig.patch.set_facecolor(SURF); ax.set_facecolor(SURF)
labels = ["情報が特定できるか", "不可逆な操作を含むか", "設計判断が要るか", "変更が広いか",
          "", "4択を1回で聞く", "4問の答えをコードで合成"]
vals = [100.0, 100.0, 100.0, 93.3, 0, 48.3, 98.3]
cols = [AQUA, AQUA, AQUA, AQUA, SURF, ORANGE, BLUE]
y = np.arange(len(labels))[::-1]
bars = ax.barh(y, vals, height=0.52, color=cols, zorder=3)
for yy, v in zip(y, vals):
    if v > 0:
        ax.text(v - 1.5, yy, f"{v:.1f}", ha="right", va="center", fontsize=11,
                color="#ffffff", weight="bold", zorder=4)
ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=10.5)
ax.set_xlim(0, 100); ax.set_xticks([0, 25, 50, 75, 100])
ax.set_xticklabels(["0", "25", "50", "75", "100%"], fontsize=9, color=INK2)
frame(ax, xgrid=True)
ax.text(101, y[0], "個別に聞いたとき", fontsize=9, color=AQUA, va="center", ha="left", weight="bold")
ax.set_title("一つずつ聞けば全部読めている。まとめて4択にすると半分になる",
             fontsize=13, color=INK, weight="bold", loc="left", pad=30)
ax.text(0, 1.06, "上4本は各条件を Noul で単独に聞いたときの正解率、下2本は最終的なルーティング先の正解率（日本語・雑談なし・各120件）",
        fontsize=8.6, color=INK2, transform=ax.transAxes)
fig.savefig(OUT + "2026-09-18_Jev使い方_図5_個別条件は読めているのに4択にすると落ちる.png",
            facecolor=SURF, bbox_inches="tight", pad_inches=0.18)
plt.close(fig)

# ---------- 図6: 校正曲線 ----------
fig, ax = plt.subplots(figsize=(6.6, 4.0), dpi=200)
fig.patch.set_facecolor(SURF); ax.set_facecolor(SURF)
mids = [0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95]
accs = [50.0, 31.4, 36.1, 22.8, 44.4, 48.8, 50.0, 55.8, 94.9]
ns = [14, 35, 61, 57, 54, 41, 36, 43, 138]
ax.plot([0, 1], [0, 100], color=GRAY, linewidth=1.4, linestyle=(0, (4, 3)), zorder=2,
        label="理想（confidence どおりに当たる線）")
ax.plot([], [], color=ORANGE, linewidth=2, label="実測（4択を1回で聞いたとき）")
ax.plot(mids, accs, color=ORANGE, linewidth=2, zorder=3)
ax.scatter(mids, accs, s=[max(30, n * 1.6) for n in ns], color=ORANGE,
           zorder=4, edgecolor=SURF, linewidth=2)
offs = [(0, 15), (0, -22), (0, 15), (0, -22), (0, -22), (0, 15), (0, -22), (0, 15), (-46, -6)]
for m, a, n, off in zip(mids, accs, ns, offs):
    ax.annotate(f"{a:.0f}%  n={n}", (m, a), textcoords="offset points",
                xytext=off, ha="right" if off[0] else "center", fontsize=8.5, color=INK2)
ax.set_xlim(0, 1); ax.set_ylim(0, 108)
ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
ax.set_xticklabels(["0", "0.25", "0.5", "0.75", "1.0"], fontsize=9, color=INK2)
ax.set_yticks([0, 25, 50, 75, 100])
ax.set_yticklabels(["0", "25", "50", "75", "100%"], fontsize=9, color=INK2)
ax.set_xlabel("返ってきた confidence", fontsize=10, color=INK2)
frame(ax, ygrid=True)
ax.legend(frameon=False, fontsize=9, loc="upper left", bbox_to_anchor=(0.02, 0.99))
ax.set_title("confidence 0.7 は「7割正しい」ではなかった",
             fontsize=13, color=INK, weight="bold", loc="left", pad=30)
ax.text(0, 1.06, "4択を1回で聞いたとき（direct）の confidence 帯ごとの実正解率。円の大きさは件数。合計480件",
        fontsize=8.8, color=INK2, transform=ax.transAxes)
fig.savefig(OUT + "2026-09-18_Jev使い方_図6_confidence07は7割正しいではなかった.png",
            facecolor=SURF, bbox_inches="tight", pad_inches=0.18)
plt.close(fig)
print("done")
