# 实验 04：用 creative-tool-scout 跑对照试验（MiniMax H3 本地部署）

**日期**：2026-10-12
**目的**：给刚写完的 `creative-tool-scout` skill 做第一次真实场景测试，并与"新手式搜索"对照。
**用户需求（原始输入）**：*"我 16 显存 8 内存，要做一个本地生成长视频。"*
**领域**：MiniMax H3 本地部署 —— 一个鱼龙混杂严重、信息更新极快的领域。

---

## 一、核心结论（先说结果）

```
用户的真实约束：显存 16GB  ✅ 够用（6GB 都能跑）
                内存  8GB  ❌ 不够（所有已知配置最低门槛 16GB，推荐 32GB，实测占用 ~44GB）

→ 本地跑 MiniMax H3 在 8GB 内存下没有已知可行配置。
→ 最便宜的解锁不是换显卡，是加内存。官方手册明确写："要不要换更大显存？不需要。"
```

**对照组的答案会是「16G 显存能跑」——这是错的**，而错的原因正是把约束读成了显存。

---

## 二、实验设计

| | 对照组 | skill 组 |
|---|---|---|
| 做法 | 新手会怎么搜（只提显存） | 严格按 `SKILL.md` 五步流程 |
| 查询 | `MiniMax 本地部署 16G显存 教程`<br>`MiniMax H3 ComfyUI 本地部署 工作流` | ①领域侦测 ②黑话翻译 ③四通道 ④活性检查 ⑤结构化输出 |

**⚠️ 污染声明**：我先跑对照组、读到了关键手册，再跑 skill 通道。
所以本次**不是盲测**，skill 的优势可能被高估。见第七节。

---

## 三、对照组结果（新手式搜索）

命中了 **5 个主要资源**：

| 资源 | 性质 |
|---|---|
| [`neng320/minimax-h3-local-deployment`](https://github.com/neng320/minimax-h3-local-deployment) | **《MiniMax H3 本地部署操作手册（消费级显卡版）》—— 消费级最佳手册** |
| 官方文档 `platform.minimax.cn/docs/guides/local-deploy-h3` | 官方部署指南 |
| HuggingFace `javawock7618/comfy-MiniMax-H3-workflows` | 工作流 |
| [`Astral-xm/ComfyUI-MiniMax-ContextIR`](https://github.com/Astral-xm/ComfyUI-MiniMax-ContextIR) | ComfyUI 节点全家桶 |
| HF `joeygambino/MiniMax-H3-Multishot-Workflow` | 多镜头工作流 |

**对照组不是没用的** —— 它拿到了这个领域最好的一份消费级手册。**这是必须承认的。**

### 但它的答案会错

同一份手册里：

- **§0 结论速览**：「16GB 显存能跑吗？→ **能，且适合**」
- **§8 避坑清单第 4 条**：「**内存 ≥32GB 是硬要求**（实测占用 ~44GB）：低显存配置下内存往往最先爆」

**新手读到 §0 就停了。** 关键词在 8 节之后。而对照组的两条查询里**根本没有"内存"这个词**——因为新手不会想到内存是瓶颈。

---

## 四、skill 组结果（按五步流程）

### 第 1 步：领域侦测

`references/` 里没有 minimax 领域包 → 走现场侦测。

- **黑话采集**：搜教程标题 → 提取出 `ComfyUI` / `pruned_int8_convrot` / `NVFP4` / `GGUF Q4` / `Turbo LoRA` / `SageAttention` / `TE-Speed` / `EasyCache` / `32 倍数对齐` / `双时钟采样`
- **天然工具清单定位**：查 `byproduct-map.md` → AI 视频领域 → 元数据 / Civitai / 工作流 JSON
- **来源**：GitHub、HuggingFace、ModelScope、Reddit r/StableDiffusion

### 第 2 步：黑话翻译

```
"本地生成长视频"  →  MiniMax H3 · FL2VA · ComfyUI · 帧插值/分段拼接
                      turbo LoRA · Sigma shift · Context Loop
"16显存"          →  16GB VRAM · offload · pruned INT8 · NVFP4 编码器
"8内存"           →  system RAM · pinned memory · mmap · 换页/分页
```

**关键**：把「8内存」翻译成了 `pinned memory` / `mmap` / `换页` —— 这一步直接决定了后面能不能找到对的东西。

### 第 3 步：四通道搜索

| 通道 | 查询 | 新捞到的（对照组没有） |
|---|---|---|
| A 黑话 | `MiniMax H3 16G显存 内存要求 量化 GGUF` | [`wildminder/awesome-minimax-H3`](https://github.com/wildminder/awesome-minimax-H3) · `ai-indeed` 内存解析 · [`wangjue520/sd-webui-forge-neo-h3`](https://github.com/wangjue520/sd-webui-forge-neo-h3) |
| **B 约束** ⭐ | `8G内存 ComfyUI 视频生成 内存不足 爆内存` | **`FlowForgeLabAi/MiniMax-H3-8GB-Workflows`** · **ComfyUI「Dynamic VRAM」** · Zenodo 8GB offload 论文 |
| C 痛点 | （同上覆盖爆内存/OOM） | OOM 处理顺序：量化降级 → 降分辨率 → 减帧 → 关音频 |
| D 溯源 | 读各来源的引用列表 | 8 个专门化仓库（见下） |

**B 通道是本轮的决定性增量。** 把"8GB 内存"这个词原样写进搜索词，直接捞出了**唯一处理内存约束的资源**。

### 第 4 步：活性检查（GitHub API 实测）

| 仓库 | 星标 | 创建 | 最近提交 | 判读 |
|---|---|---|---|---|
| [`wildminder/awesome-minimax-H3`](https://github.com/wildminder/awesome-minimax-H3) | **561** | 2026-08-04 | **2026-10-08** | ✅ 最活跃的策展资产（2 基准 + 17 社区报告） |
| [`neng320/minimax-h3-local-deployment`](https://github.com/neng320/minimax-h3-local-deployment) | 76 | 2026-08-06 | 2026-08-12 | ⚠️ 2 个月未更新，但内容仍是消费级最佳手册 |
| [`Argus-AiTeam/minimax-h3-mac`](https://github.com/Argus-AiTeam/minimax-h3-mac) | 47 | 2026-08-10 | 2026-08-12 | Apple Silicon MLX 路线 |
| [`Astral-xm/ComfyUI-MiniMax-ContextIR`](https://github.com/Astral-xm/ComfyUI-MiniMax-ContextIR) | 41 | 2026-08-05 | 2026-09-12 | 活跃 |
| **`FlowForgeLabAi/MiniMax-H3-8GB-Workflows`** | **16** | 2026-09-19 | 2026-09-25 | ✅ **唯一处理内存约束的资源** |
| [`shiqikuangsan31/MiniMax-H3-12GB-ComfyUI-Guide`](https://github.com/shiqikuangsan31/MiniMax-H3-12GB-ComfyUI-Guide) | 8 | 2026-08-11 | 2026-08-11 | 12GB 档指南 |
| **`wangjue520/sd-webui-forge-neo-h3`** | **2** | **2026-10-07** | 2026-10-07 | 🔥 **5 天前创建**，另一条路线（Forge Neo） |
| `sepiablue-ai/minimax-h3-turbo-lora-benchmark` | 0 | 2026-08-13 | 2026-08-13 | 0 星，却被 awesome 列表当基准引用 |

**「星标 ≠ 价值」在本轮被三次验证**：
- 最佳消费级手册只有 **76★**
- 唯一处理低内存的资源只有 **16★**
- 一条完整替代路线只有 **2★**、**5 天前**才出现

> 最后一条再次印证实验 01 的时间证据：**5 天前诞生的东西，任何静态清单在物理上不可能收录。**

### 第 5 步：三个独立来源交叉验证「内存是硬门槛」

| 来源 | 原文 |
|---|---|
| `neng320` 手册 | 「16GB 显存 + **≥32GB 内存**」；实测占用 **~44GB**；「**内存 ≥32GB 是硬要求**：低显存配置下内存往往最先爆」 |
| `wildminder` 性能报告 | 8GB 显存档：「**RAM: ≥32 GB required, 64 GB recommended**」；6GB 档：「RAM ≥24 GB」；12GB 档：「32 GB works, **64 GB RAM is the root-cause fix**」 |
| `FlowForgeLabAi` 8GB 工作流 | 「`--disable-pinned-memory` ← **16 GB 内存机器【必须】**」；「对 **16 GB 内存的机器**这是关键差别」 |

**三份独立来源，最低门槛一致：16GB（需特殊参数），推荐 32GB，实测 44GB。用户的 8GB 低于全部。**

---

## 五、对照分析：增量在哪

| 维度 | 对照组 | skill 组 |
|---|---|---|
| **答对"内存够不够"** | ❌ 会答"16G显存能跑" | ✅ **显存够、内存不够，本地不可行** |
| 命中资源数 | ~5 | **~13** |
| 低内存专门资源 | ❌ | ✅ 16★ 工作流包 + `--disable-pinned-memory` |
| 社区策展资产 | ❌ | ✅ 561★ awesome 列表（2 基准 + 17 报告） |
| 替代路线 | 部分 | ✅ Forge Neo / Apple MLX / DGX Spark / 6GB INT4 |
| 上下限边界 | ❌ | ✅ 最低 16GB / 推荐 32GB / 实测 44GB |
| 活性读数 | ❌ | ✅ 8 个仓库的星标与提交时间 |
| 硬件风险预警 | ❌ | ✅ 见第六节「已知坑」 |

**根本差异**：对照组的查询里没有"内存"二字。**skill 强制把用户的全部约束写进搜索词**——这就是 `SKILL.md` 第 2 步 B 通道存在的理由。

---

## 六、skill 的最终输出（按 SKILL.md 第 5 步格式）

### ⛔ 结论先行：你这个配置，本地跑不了

不是显卡的问题——**16GB 显存对 MiniMax H3 完全够用**（6GB 显存都有社区验证配置）。
**卡在 8GB 内存上。** 最低门槛是 16GB（还需特殊启动参数），推荐 32GB，参考配置实测占用 ~44GB。

---

### 主路径：加内存后跑 ComfyUI 消费级路线 ⭐

**适合谁**：愿意加一条内存（通常比换显卡便宜一个数量级），想在本机出片。

```
要装什么：
  1. ComfyUI 官方整合包 v0.30.0+（INT8 硬性依赖 torch cu130，第三方包必翻车）
     https://github.com/Comfy-Org/ComfyUI/releases/download/v0.30.0/ComfyUI_windows_portable_nvidia.7z
  2. 模型组合（共约 40GB，走 ModelScope 国内直连）
     modelscope.cn/models/Comfy-Org/MiniMax-H3
       diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors   19.5G
       text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors          14.6G
       vae/minimax_h3_video_vae_fp16.safetensors                            4.9G
       vae/minimax_h3_audio_vae_fp32.safetensors                            0.6G
     ⚠️ 文本编码器必须用 nvfp4_awq（比 int8 小 10.7GB）—— 对内存紧张是关键
     ⚠️ DiT 主模型必须 INT8 ConvRot（4bit 损失运动细节）
  3. 磁盘预留 80–100GB（只用 FL2VA 组合）

启动参数（低内存必加）：
  --disable-pinned-memory

参考工作流（内存受限专用，16★）：
  github.com/FlowForgeLabAi/MiniMax-H3-8GB-Workflows
  → H3_Balanced.json（8 步 + turbo LoRA，10 秒成片约 14 分钟）

活性：
  2026-09-25 最后提交 · 16★ · 未归档  ⚠️ 星标很低，但它是唯一处理内存约束的资源
  neng320 手册 2026-08-12 后未更新 · 76★（内容仍有效）

已知坑（都来自实测）：
  · 内存 ≥32GB 是硬要求，实测占用 ~44GB；低显存配置下内存最先爆
  · 每次跑之前必须重启 ComfyUI —— 连续跑 1.7 小时后单 block 从 0.9s 掉到 212s
    判断方法：看 nvidia-smi 功耗，正常 64–98W，在换页会变平线 34–36W
    （利用率仍显示 99% —— 那个计数器把搬运内存的核也算进去了）
  · 分辨率必须是 32 的倍数，否则崩 patchify_video
  · "百万像素"是陷阱：填 1.0MP 配 3:4 会得到 896×1184，短边超训练区间反而更差
  · VAE Decode 前加 VRAM-Cleanup 节点，防 100% 处崩溃
  · SageAttention 与 --use-sage-attention 二选一，勿重复
  · 6GB/低显存激进配置有真实硬件风险：有 RTX 4050 6GB 用户持续重载后 GPU 物理损坏
  · 许可证排除美/欧/英/韩地区；中国可用，商用前自查协议
```

### 备选 1：不动硬件 —— 走云 / 免费算力

```
适合谁：只想先看看效果，或者偶尔出片
  · OpenI 启智社区免费算力（T4 / 910B / A100）—— 先测再决定要不要投入
  · RunningHub 在线工作流（直接搜"H3"，注册送额度）
  · MiniMax 官方 API —— 唯一完整 2K 链路（含 H3-Regenerate-2K）
  · AutoDL 等云 GPU —— 批量生产时按需
活性：均为在运营的服务（未逐个验证价格与额度）
```

### 备选 2：换技术路线（内存仍需 32GB+，收益有限）

```
适合谁：不想用 ComfyUI，或用的是 Forge 生态
  · Forge Neo 路线：github.com/wangjue520/sd-webui-forge-neo-h3
    12GB 显卡可跑 GGUF Q4，含溢出自愈
    ⚠️ 2★，2026-10-07 创建（5 天前）—— 极新，未经验证
  · Apple Silicon：github.com/Argus-AiTeam/minimax-h3-mac（MLX streaming，47★）
    需 24GB+ 统一内存
  · 6GB 显存档：INT4 ConvRot + ≥24GB 内存
```

### 为什么推荐主路径而不是别的

**因为你的显存是够的，只有内存不够。** 官方手册明确写：「**要不要换更大显存？不需要。24GB 只减少卸载，计算速度提升不足以抵消换卡成本。**」

**加内存是这个配置下唯一的低成本解锁**；云算力是不想动硬件时的替代；换路线解决不了内存问题。

---

## 七、局限与污染声明

1. **不是盲测。** 我先跑对照组、读到了 `neng320` 手册，之后才跑 skill 通道。skill 的优势可能被高估。
2. **执行者就是作者**（我写的 skill，我跑的流程），存在确认偏误。
3. **单次实验，未重复测量。**
4. 对照组并非无价值——它拿到了该领域最好的消费级手册。**本轮 skill 的增量是"约束定位 + 来源广度 + 活性读数"，不是"找到对照组完全找不到的东西"。**
5. 我未实际部署验证，所有性能数字来自他人实测报告。

---

## 八、本次实验对 skill 本身的反馈（重要）

### ✅ 被验证有效的

| 机制 | 证据 |
|---|---|
| **领域侦测** | `references/` 里没有 minimax 包，流程仍完整跑通 |
| **约束通道（B）** | 本轮的决定性增量 —— 捞出唯一处理内存约束的资源 |
| **活性检查** | 发现 76★ / 16★ / 2★ 三个低星高价值资源，避免"唯星标论" |
| **失败时直说** | 结论是"本地不可行"，不是硬凑一套配置 |

### ⚠️ 需要修的地方

**1. `byproduct-map.md` 的分类不完整——这是本轮最重要的发现。**

我之前把「天然工具清单」等同于 MMD 那种**署名标注**。但在这个领域，真正的工具来源完全不同：

| 实际起作用的来源 | 例子 | 星标 |
|---|---|---|
| **社区基准/awesome 汇总** | `wildminder/awesome-minimax-H3`（2 基准 + 17 现场报告） | 561 |
| **约束专门化的工作流包** | `FlowForgeLabAi/MiniMax-H3-8GB-Workflows` | 16 |
| **平台官方文档** | `platform.minimax.cn/docs/guides/local-deploy-h3` | — |

→ **`byproduct-map.md` 需要新增一类**：「**技术类领域**：靠社区基准报告 / 约束专门化配置包 / 官方文档，而不是署名标注」。

**2. "工具名不在标题里"被证伪（跨领域）。**

本领域资源名**就在标题里**（`MiniMax-H3-8GB-Workflows`、`MiniMax-H3-12GB-ComfyUI-Guide`）。
→ 这验证了实验 01 报告里的诚实声明是对的：**MMD 的 98.2% 结论不能外推**。
→ SKILL.md 核心原则 1 需要加限定：**"在署名文化强的领域成立；技术类领域资源常直接写在标题/仓库名里"**。

**3. 约束通道依赖用户说全约束。**

用户这次说了"16 显存 8 内存"，所以能定位。**如果他只说"16 显存"，B 通道就会失效。**
→ 第 0 步应该把「内存/RAM」列进**必问清单**，而不是等用户主动说。

### 本次实验的净结果

**skill 通过了第一次真实测试**，但暴露出 `byproduct-map.md` 的分类缺口和一条核心原则的适用范围问题。
这两处修掉之后，它对"技术类领域"的覆盖才算完整。
