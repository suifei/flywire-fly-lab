#!/usr/bin/env python3
"""
把日志 §46（五子棋 v2）从结果文件**渲染**出来，写进 docs/log/report.md 的 <!-- §46:begin --> … <!-- §46:end --> 之间。
这一节数字太多，手抄必错（本项目最大的错误来源就是手抄数字，见 AGENTS.md）。叙述是手写的，数字全部取自 JSON。
用法：python3 scripts/render_report46.py          （流水线重跑之后再执行一遍即可）
"""
import json, re, sys
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent; R = ROOT / "results/gomoku"
J = lambda f: json.loads((R / f).read_text())
S = J("lines_summary.json"); T = S["train"]; A = T["arms"]; P = S["play"]; DS = S["dataset"]; RL = S["rl"]
pct = lambda v: "—" if v is None else f"{v * 100:.1f}%"
wl = lambda r: "—" if not r else f"{r['win']}–{r['loss']}" + (f"–{r['draw']}" if r.get("draw") else "")
NAME = dict(fly_intact="果蝇脑 · 真实连接组", fly_shuffled="果蝇脑 · 打乱接线", raw24="不经过脑子（24 个输入通道）",
            rand_relu="同维度的随机 ReLU 网络", free_table="每种线型一个自由参数", teacher_table="老师的手写分值（不训练）")
fi, fs_, rw, rr = A["fly_intact"], A["fly_shuffled"], A["raw24"], A["rand_relu"]
yes = lambda b: "**成立**" if b else "**不成立**"
_cap = fs_.get("capped")
CAPTXT = (f"这一版两个臂的读出维度相同（打乱接线活跃的特征列有 {_cap['active']:,} 个，随机取了 {_cap['used']:,} 个）——维度相同它仍然不输；" if _cap
          else f"打乱之后活跃的神经元多一倍（{fs_['dim'] - 1:,} 对 {fi['dim'] - 1:,}），读出维度更高；")

rows_train = "\n".join(
    f"| {NAME[k]} | {v.get('dim', '—')} | {v.get('distill_r2', '—')} | {pct(v.get('stage1_test_top1'))} | {pct(v['test_top1'])} | "
    f"{pct(v.get('test_top1_testseeds')) if k.startswith('fly') else '—'} | {pct(v.get('wine_top1'))} |" for k, v in ((k, A[k]) for k in NAME if k in A))
OPP = ["random", "old_teacher", "teacher2_d4", "teacher2_d6", "teacher2_d8"]
rows_play = "\n".join(f"| {NAME[k]} | {'直觉' if d == 'd1' else d[1:] + ' 步'} | " + " | ".join(wl(row.get(o)) for o in OPP) + " |"
                      for k in NAME if k in P["engine"] for d, row in P["engine"][k].items())
hh = P["head_to_head"]; cA, cA2, cC2 = P["criterion_A"], P["criterion_A2"], P.get("criterion_C2")
lad = " / ".join(f"深度 {r['depth']}：{wl(r)}" for r in S["teacher_ladder"]["rows"])
noise = "\n".join(f"| {r['r2']} | {wl(r)} | {pct(r['win_rate'])} |" for r in S["table_noise"]["rows"])
tim = "\n".join(f"| {r['depth']} | {r.get('nodes', '—'):,} | {r.get('seconds', '—')} |" for r in S["depth_timing"]["rows"] if r.get("nodes")) if "depth_timing" in S else ""
sw = S.get("search_width", {}).get("rows", []); vv = S.get("vcf_value", {}).get("rows", [])
DM = S.get("depth_models")
NV = len(T.get("feat_sets", [""])); VR = S.get("views_r2", {}); VA = S.get("view_adoption"); OV = S.get("one_view")
sa = S["seed_averaging"]; ol = S["opto_leak"]; sf = S["score_forms"]; pr = S["class_probe"]; rs = S.get("rl_small")
sv = S["shape_values"]; cn = S["class_names"]
shape_tbl = "| 类别 | " + " | ".join(cn) + " |\n|---|" + "---|" * 9 + "\n| 这类有多少种线型 | " + " | ".join(str(c) for c in S["class_counts"]) + " |\n" + \
    "| 老师的 ln(分值+1)（阶段一的目标） | " + " | ".join(f"{v:.1f}" for v in sv["teacher"]["log_att"]) + " |\n" + \
    "| **果蝇学到的**（类内平均对数价值） | " + " | ".join(f"**{v:.1f}**" for v in sv["fly_intact"]["log_att"]) + " |\n" + \
    "| 打乱接线 | " + " | ".join(f"{v:.1f}" for v in sv["fly_shuffled"]["log_att"]) + " |"

text = f"""<!-- §46:begin （本节由 scripts/render_report46.py 从结果文件渲染；要改数字请重跑流水线再渲染，不要手改）-->
## 46. 五子棋 v2：从「几乎随机」到能和搜 6 步的老师下平——以及 v1 为什么全部作废（2026-09-19/20）【实测】

用户的目标：**提高果蝇下五子棋的能力**。原话是「棋力太弱智，训练是否出了问题？」——**是的，出了问题，而且是两层。**

### 46.1 第一层：一个 bug，让 v1 的全部数字作废

`brain.setOpto` 换一批神经元时**不清上一批的 stimProb**。五子棋 v1 的特征提取对每个局面调一次 `setOpto`，
于是输入一个接一个地叠上去，几次之后所有输入神经元都在放电，特征里几乎不含当前局面的信息。
`gomoku/test_engine.js` 每次都把旧行为重演一遍存证（`opto_leak.json`）：线型 A 单独喂进去是 **{ol['fixed']['A_first']}** 个脉冲、B 是 {ol['fixed']['B']:,} 个；
**先喂过 B 再喂 A，得到 {ol['old_behaviour']['A_after_B']:,} 个**，逐神经元与真正的 A 相差 {ol['old_behaviour']['abs_diff_vs_true_A']:,}。修复后 A → B → A 的两次 A 逐位相同（差 {ol['fixed']['abs_diff_A_first_vs_again']}）。

发现的经过值得记：换成线型输入之后先探测了 300 种线型，**只得到 17 种不同的特征**、数值秩 16——这不可能是对的，顺着查到的。
§38.4 / §41.6 里 v1 的结论（一致率 0.021、打乱 0.019、「连接组对下棋没有贡献」、26/40、0:40）**全部作废**：
那个实验本身是坏的，它既不支持也不否定任何关于连接组的说法。
**游戏不受影响**：`game_core` 每一步都用 `setRate` 把输入组整组重写；修复前后 7 个任务 + 10 个突变体的结果逐项相同（实测对比过）。

**教训**：一个「几乎等于随机」的阴性结果，第一反应应该是查输入有没有真的送进去。当时连「不同局面的特征是否不同」都没看过。

### 46.2 第二层：架构。把整盘棋铺进脑子，丢掉了五子棋最要紧的两条性质

v1 把 225 格 × 2 个通道随机铺到感觉神经元上：同一个「活三」出现在棋盘不同位置，是两个毫不相干的输入（没有平移不变性）；
「连成五」是 5 个格子的与运算，线性读出在那个表示上算不出来（直接看棋盘的线性读出也只有 0.17）。

v2 的单位是**线型**：候选点某个方向两侧各 4 格，每格 ∈ {{空, 我方, 对方, 边界}}。合法线型恰好 **{DS['patterns_total']:,}** 种
（边界只能从外侧连续进来：(81+27+9+3+1)² ），少到可以让果蝇脑**把每一种都跑一遍**：
8 格 × 3 种状态 = 24 个通道，各接约 61 个真实感觉神经元（分配表固定种子打乱，是任意的），160 Hz 泊松驱动 300 ms，
数下游神经元的脉冲，3 个泊松种子取平均。这样的分配表一共用了 **{NV} 套**（「视角」，见 46.8），拼起来是 {fi['dim'] - 1:,} 维特征。**脑子里一个突触都不训练**，训练的只有一层线性读出：

    a[线型] = Φ̄·w （这条线的对数价值）      落子分 = Σ_4方向 e^{{a[进攻线]}} + λ·Σ_4方向 e^{{a[防守线]}}      防守线 = 同一条线互换视角

「想 N 步」是把 e^a 这张表交给 alpha-beta 搜索。**搜索只懂规则**（成五 = 赢、对手能成五就必须挡、黑方禁手问规则引擎），不含任何棋形分值。
每走一步，页面把这一步的线型**放进真脑里现场重跑**，与表比对，相对偏差在 10⁻⁶ 量级（`test_engine.js` 第 6 项、浏览器测试都在查）。

### 46.3 训练数据

- **老师 v2**（`teacher2.js`）：线型按**递归定义**分成 9 类（成五 / 活四 = 有 ≥2 个点能成五 / 冲四 / 活三 = 再下一子能变活四 …），
  分值手选，棋力来自 alpha-beta。对深度 3 各 30 局：{lad}。
- **局面**：{DS['n_games']} 局混合水平自对弈（双方各自随机取深度 1–4，20% 概率从前 5 名里随机挑），**{DS['n_positions']:,} 个局面**，
  每个都标了深度 1–6 与 8 的最佳着（用户要的「推理 1–6 步的训练数据」）；各深度与深度 8 一致的比例：""" + \
    "、".join(f"深度 {d} {pct(v)}" for d, v in DS["agree_with_depth8"].items() if d != "8") + f"""。按整局切分（训练 {T['n_train']:,} / 验证 {T['n_val']:,} / 测试 {T['n_test']:,}）。终局胜负是事后重放补的，{DS['n_positions']:,} 个局面逐个核对一致。
- **外部考卷**：HuggingFace `Karesis/Gomoku`（MIT；Wine 引擎自对弈 {DS['wine']['n_games']} 局），可用 **{DS['wine']['n']:,}** 个局面
  （剔除黑方落在连珠禁手点的 {DS['wine']['dropped']['black_forbidden_under_renju']} 个、落在已有子上的 {DS['wine']['dropped']['occupied']} 个）。
  **只考不训**——我们自己的测试集是「与自己写的老师一不一致」，有自己出题自己判的嫌疑；Wine 是别人的引擎。
  KataGo 蒸馏数据集（5 种规则各约 5000 万局面）没有用：这个模型的容量瓶颈在读出层（见 46.6），不在标签质量。

### 46.4 五个坑（每个都有实测数字）

1. **两张表不可识别。** 第一版学进攻、防守两张表。但进攻线型与防守线型一一对应，读出层只能约束两者之和——
   单看进攻表，「成五」的均值 −0.68、「无」+0.17。改成只学一张进攻价值表，防守 = λ × 对手的进攻价值。
2. **对数尺度的量不能直接相加。** 一条活四线 + 三条空线的和，小于四条活二线。同一张表（老师的 ln 分值）只看 1 步对旧老师：
   直接相加 **{wl(sf['sum_of_logs'])}**，每条线取指数再相加 **{wl(sf['sum_of_exps'])}**（`score_forms.json`）。
3. **着法标签只约束出现过的线型。** 训练局面里只出现过 **{DS['patterns_seen_in_dataset']:,} / {DS['patterns_total']:,}** 种；只用着法标签训练时其余的价值随意漂移
   （成五类的均值被学成 −6.67），搜索一走进没见过的局面就崩（想 2 步以上 0:16）。
   所以**阶段一先蒸馏整张评分表**（用户的第一条建议：把落子评分算法当训练数据），阶段二再用着法标签微调并加锚定。
4. **读出层会吃泊松噪声。** 这正是事先写好的判据 D 要抓的：单种子 60 ms 窗，换种子一致率掉 32 个百分点；300 ms 掉 17；3 种子平均掉 5.3；
   训练时每步随机抽 3 个种子取平均（噪声增广）→ **掉 {fi['seed_drop'] * 100:.1f} 个百分点**，通过。代价是一致率少约 3 个点。
   想靠加维度提精度是死路：分 3 个时间段 + 第二套输入分配，维度 1,830 → 10,637，样本内 R² 0.866 → 0.976，**换种子后 R² 0.756 → 0.386**。
   多平均几次试次才是正路，但很快饱和（平均 1/2/3/4 个种子，换种子 R² = {sa['1']['r2_new_seeds']:.3f} / {sa['2']['r2_new_seeds']:.3f} / {sa['3']['r2_new_seeds']:.3f} / {sa['4']['r2_new_seeds']:.3f}）。
5. **线型窗口只看两侧各 4 格。**「中心 + 一侧 4 子」在窗口里是五连，第 5 格外还有黑子就是长连禁手。黑方的五连要再问一次规则引擎；
   必败局面（对手有两个成五点、挡点又是禁手）也得走出一步合法的棋。由随机局面的合法性测试抓到，现在是 `test_engine.js` 第 4 项。

### 46.5 结果一：同一套训练，换六种特征

| 线型特征来自 | 维数 | 阶段一 R² | 只做阶段一 | 测试一致率 | 换一组种子 | 外部考卷 Wine |
|---|---|---|---|---|---|---|
| 随机猜 | — | — | — | {pct(T['random_top1'])} | — | {pct(T['wine_random_top1'])} |
{rows_train}

「一致率」= 第一选择与深度 8 老师的最佳着相同。事先写好的判据：

- **B 脑子有用**（比不经过脑子高 ≥ 5 个百分点）→ {yes(T['criterion_B_brain_helps'])}：{pct(fi['test_top1'])} 对 {pct(rw['test_top1'])}。
- **C 接线有用**（比打乱接线高 ≥ 5 个百分点）→ {yes(T['criterion_C_wiring_helps_top1'])}：{pct(fi['test_top1'])} 对 {pct(fs_['test_top1'])}。
  {CAPTXT}**同维度的随机 ReLU 网络（{pct(rr['test_top1'])}）也不输果蝇脑**。
  所以能说的是「这颗脑子是一个够用的非线性展开」，**不能说「真实接线对下棋有特殊贡献」**。
- **D 不是噪声哈希**（换一组从未见过的泊松种子，掉幅 ≤ 5 个百分点）→ {yes(T['criterion_D_not_noise_hash'])}：掉 {fi['seed_drop'] * 100:.1f} 个百分点。

果蝇**从没见过「活三」「冲四」这些类别**（类别只用来给学到的价值分组），它自己排出的顺序{'全部正确' if sv['fly_intact']['order_ok'] else '有颠倒'}：

{shape_tbl}

另一个不依赖棋局的直接检验（`line_class_probe.json`）：只用放电线性读出 9 类棋形，留出 20% 线型，果蝇脑 {pr['intact']['heldout_patterns']:.3f}、
不经过脑子 {pr['raw24']['heldout_patterns']:.3f}、打乱接线 {pr['shuffled']['heldout_patterns']:.3f}（多数类基线 0.612）——**泛化到没见过的线型很差**，
关键棋形的召回更差（活四 {pr['intact']['recall']['7']:.3f}）。所以这条路能成，靠的是 14,641 种线型可以**全部枚举**，不需要泛化。

### 46.6 结果二：真下。棋力主要来自搜索深度

所有臂用**同一个引擎**，差别只在塞进去的那张价值表。每格 = 胜–负（–和），每组 {P['games_per_match']} 局（深度 8 的老师 20 局）：

| 谁的价值表 | 想几步 | 对随机 | 对旧老师（v1 的对手） | 对老师搜 4 步 | 对老师搜 6 步 | 对老师搜 8 步 |
|---|---|---|---|---|---|---|
{rows_play}

- **判据 A 棋力达标**（只凭直觉对旧老师 ≥ 50%、对随机 ≥ 95%）→ {yes(cA['passed'])}：{pct(cA['vs_old_teacher'])}、{pct(cA['vs_random'])}（v1：{cA['v1']['vs_teacher']}、{cA['v1']['vs_random']}）。
- **判据 A2 搜索有用**（想 6 步对老师搜 4 步 ≥ 50%）→ {yes(cA2['passed'])}：{pct(cA2['d6_vs_teacher2_d4'])}。
- **判据 C2 接线有用**（真实接线对打乱接线，同为想 4 步，≥ 60%）→ {yes(cC2['passed']) if cC2 else '—'}：{pct(cC2['intact_vs_shuffled_d4']) if cC2 else '—'}。
  正面交锋：直觉 {wl(hh.get('d1'))}、想 4 步 {wl(hh.get('d4'))}、想 6 步 {wl(hh.get('d6'))}。

**表的精度值多少棋力**（`table_noise.json`：给老师的对数分值表加高斯噪声，同一个引擎想 4 步，对老师搜 4 步）：

| 加噪后对原表的 R² | 胜–负 | 胜率 |
|---|---|---|
{noise}

果蝇的表阶段一 R² 只有 {fi['distill_r2']}，实战却不在这条曲线的 0.85 那一档上——阶段二的微调把误差挪到了不要紧的线型上。
但精度这条路的余量有限（46.4 第 4 条），**真正的杠杆是深度**：

| 搜索深度 | 节点数 | 用时（秒，受机器负载影响） |
|---|---|---|
{tim}

""" + (f"引擎每层只展开落子分最高的 K 个点。同等节点预算（每步 2 万）下：" + "；".join(f"宽度 {r['K_a']} 对 {r['K_b']} = {wl(r)}（平均深度 {r['mean_depth_a']} 对 {r['mean_depth_b']}）" for r in sw) +
       "。6 明显好于 10（收窄之后搜得更深）；4–6 之间在 100 局的噪声里分不出高下，默认取 6。\n" if sw else "") + \
      (f"连续冲四的杀棋模块（攻 + 防）**没测出增益**：" + "、".join(f"想 {r['depth']} 步 {wl(r)}" for r in vv) + "（各 100 局）——搜索里被迫的应手本来就不消耗深度。模块保留，但别指望它。\n" if vv else "") + f"""
**一次差点写进结论的错误**：比较「只做阶段一」与「阶段一 + 二」时，先看到前者对老师 18–21–1、后者 12–28，就要下「微调让搜索变弱」的结论。
正面交锋一测：直觉 13–22–5、想 4 步 15–24–1、想 6 步 20–20——并不更差。每组 40 局的标准差就有 8 个百分点，15 个点的差别分不开。
**做取舍用的对比至少 100 局，并且用节点预算而不是时间预算（不受机器负载影响）。**

### 46.7 结果三：自对弈强化（用户提的「链接多巴胺」）——阴性

三因子规则只改读出层：Δw = 学习率 × **δ** × 资格迹，δ = 这一局的结果 − 近期平均（奖励预测误差）。
**这个模型自己的多巴胺神经元在非失控条件下不放电（§11：PAM 0/307），所以 δ 是在连接组外面算的**，页面上也这么写。
判据（事先写好）：{RL['criterion']}。

- 主实验（{RL['iters']} 轮 × {RL['games_per_iter']} 局，学习率 {RL['lr']}）：想 4 步对监督版 **{wl(RL['final']['d4_vs_supervised_d4'])}（{pct(RL['win_rate_vs_supervised'])}）→ {'通过' if RL['criterion_passed'] else '不通过'}**；只凭直觉 {wl(RL['final']['greedy_vs_supervised'])}。
""" + (f"- 探索性地再跑一次（{rs['iters']} 轮 × {rs['games_per_iter']} 局，学习率 {rs['lr']}）：{wl(rs['final']['d4_vs_supervised_d4'])}（{pct(rs['win_rate_vs_supervised'])}）→ {'通过' if rs['criterion_passed'] else '同样不通过'}。\n" if rs else "") + f"""
每轮几十局的胜负信号太吵，推不动一个 {fi['dim']:,} 维的读出层。**页面上的果蝇用的是监督训练（阶段一 + 二）的表**，强化版只在图里展示训练曲线。

### 46.8 多给几套输入分配（视角）：读出更准，棋也更好一点——第二次尝试才过

「视角」= 把 24 个通道分给另一批输入神经元的另一张随机分配表。每个视角都要把 14,641 种线型重跑一遍（× 9 个种子 × 两个臂，后台跑了约 4 小时）。
换一组种子后对评分表的拟合 R²（`two_views.json`）：""" + ("、".join(f"{k} **{v['r2_new_seeds']}**" for k, v in VR.items()) if VR else "—") + f"""。到 3–4 个视角就饱和了，这颗脑子可靠的上限在 R² ≈ 0.90。

换不换表，判据事先写死：**新表对旧表，同一个引擎都想 6 步，200 局，胜率 ≥ 55% 才换**。
""" + (f"""
| | 新表对旧表（想 6 步） | 只凭直觉 | 各自对老师搜 6 步 |
|---|---|---|---|
| 第一次（阶段一的岭系数固定为 10） | **{wl(VA['attempt1_fixed_ridge']['head_to_head'])}（{pct(VA['attempt1_fixed_ridge']['win_rate'])}）→ 不换** | {wl(VA['attempt1_fixed_ridge']['greedy_head_to_head'])} | 新 {wl(VA['attempt1_fixed_ridge']['vs_teacher_d6']['new'])}、旧 {wl(VA['attempt1_fixed_ridge']['vs_teacher_d6']['old'])} |
| 第二次（每个臂自己选岭系数后重训） | **{wl(VA['attempt2']['head_to_head'])}（{pct(VA['attempt2']['win_rate'])}）→ 换** | {wl(VA['attempt2']['greedy_head_to_head'])} | 新 {wl(VA['attempt2']['vs_teacher_d6']['new'])}、旧 {wl(VA['attempt2']['vs_teacher_d6']['old'])} |
| 独立确认（换一批开局） | {wl(VA['confirm']['head_to_head'])}（{pct(VA['confirm']['win_rate'])}） | {wl(VA['confirm']['greedy_head_to_head'])} | 新 {wl(VA['confirm']['vs_teacher_d6']['new'])}、旧 {wl(VA['confirm']['vs_teacher_d6']['old'])} |

第一次没过的原因是个真缺陷：岭系数固定为 10，维度一多就去拟合噪声（同一次训练里打乱接线的臂有 14,070 维 ≈ 线型总数，一致率直接崩到 23%）。
改成每个臂用前一半训练种子拟合、在后一半训练种子上选岭系数（测试种子不碰），选出来的是 {fi.get('ridge_alpha', '—')}。
**这是第二次尝试，两次都写在这里**；确认赛用的是另一批开局。提升是小幅的：对老师搜 6 步，新旧两张表没有差别。
""" if VA else "") + (f"""
单视角时的数字留档（`*_1view.json`）：一致率 {pct(OV['fly_intact']['test_top1'])}、换种子 {pct(OV['fly_intact']['test_top1_testseeds'])}、Wine {pct(OV['fly_intact']['wine_top1'])}、阶段一 R² {OV['fly_intact']['distill_r2']}；
想 6 步对老师搜 4 / 6 / 8 步 {wl(OV['play_fly_intact']['d6']['teacher2_d4'])} / {wl(OV['play_fly_intact']['d6']['teacher2_d6'])} / {wl(OV['play_fly_intact']['d6']['teacher2_d8'])}。46.5–46.7 的表都是 {NV} 个视角的结果。
多视角时打乱接线的臂**只随机取与真实接线一样多的特征列**（它活跃的神经元多一倍，全取有 14,070 维，既不公平也放不进内存）。
""" if OV else "") + f"""
### 46.9 「推理必须是训练出来的」：多步推理能训练进读出层多少（`gomoku/depth_models.js`）

用户的要求（2026-09-20）：页面上的多步推理必须是训练好的模型给的，不能是下棋时现跑的搜索算法。
数据集里每个局面本来就标了向前搜 1–6、8 步各自的最佳着，于是对每个 N 各训练一个读出层；**下棋时只做模型推理**（线型 → 果蝇脑特征 → 这个读出层 → 落子分最大的点），页面的「推理步数」选的就是用哪一个。
""" + ("| 推理步数 | 与自己的标签一致 | 与深度 8 一致 | 对随机 | 对旧老师 | 对老师搜 1 步 | 对老师搜 2 步 | 对老师搜 4 步 | 对「1 步」的模型 |\n|---|---|---|---|---|---|---|---|---|\n" +
  "\n".join(f"| {d} | {pct(DM['train'][d]['agree_own_label'])} | {pct(DM['train'][d]['agree_depth8'])} | {wl(v['random'])} | {wl(v['old_teacher'])} | {wl(v['teacher2_d1'])} | {wl(v['teacher2_d2'])} | {wl(v['teacher2_d4'])} | {wl(DM['vs_d1_model'].get(d))} |" for d, v in DM["vs"].items()) +
  f"\n\n判据（写在训练之前）：{DM['criterion']['text']} → **{'成立' if DM['criterion']['passed'] else '不成立'}**（{pct(DM['criterion']['win_rate'])}，和棋算未胜）。\n"
  "**多步推理基本训练不进这种读出层**：它只能给每条线一个价值再相加，「向前看」需要的组合推理表达不了。7 个模型彼此差不多，都在旧老师（只看 1 步的手写启发式）的水平；\n"
  "同一张表交给搜索，棋力的差距全部来自搜索（46.6）。页面默认用纯模型推理，alpha-beta 只作为默认关闭、标明「算法，不是果蝇」的外挂。\n" if DM else "（尚未训练）\n") + f"""
### 46.10 能说什么、不能说什么

- **能说**：果蝇脑 + 一层线性读出，学会了给每条线估价，顺序全对；放进只懂规则的搜索，想 6 步能和搜 4–6 步的手写老师下平或占优。v1 是几乎随机。
- **不能说**：「真实连接组对下棋有特殊贡献」（打乱接线、随机网络都不输）；「果蝇在思考」（外挂搜索里向前推演是算法做的；纯模型推理时它没有向前看的能力，见 46.9）；「多巴胺让它学会了下棋」（阴性，而且 δ 不是它自己的）。
- 页面卡片、台账、这一节都从 `results/gomoku/lines_summary.json` 取数。
<!-- §46:end -->"""

rep = ROOT / "docs/log/report.md"; s = rep.read_text()
if "<!-- §46:begin" in s: s = re.sub(r"<!-- §46:begin.*?<!-- §46:end -->", lambda m: text, s, flags=re.S)
else: s = s.rstrip() + "\n\n" + text + "\n"
rep.write_text(s)
print(f"§46 已渲染（{len(text):,} 字符）")
