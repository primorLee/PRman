# PRman 初始发布版安全与工程审查

> 归档日期：2026-08-29  
> 审查对象：当时 `main` 上的初始发布版本  
> 状态：作为修复工作的原始审查记录保留；其中部分描述会随着后续实现变更而过时。

## 结论

我审查的是当前 `main` 上的初始发布版本，包括核心 Python 代码、评分器边界、决策算法、JSON Schema、Skill、Plugin manifest、测试和 CI。GitHub Actions 当前是绿色的，但仓库自己的路线图仍把生产评分器、证据伪造测试、全新 Codex 任务安装验证和 Draft PR 确认链路列为未完成。整体判断是：**这是一个结构清晰的 M0/pre-alpha 原型，不适合充当生产环境的 PR 准入门禁。**

下面的严重度按“把它用作生产 PR gate 时的影响”评定，不是正式 CVSS。

## 1. 严重：所谓“非可信评分器”实际上拥有进程内任意代码执行权

外部 Python 评分器通过 `entry_point.load()` 加载，然后直接在 PRman 进程里执行 factory 和 `provider.score()`。这意味着一个被入侵或恶意的评分器不只是能返回假分数，还能：

* 读取环境变量、凭证和私有源码；
* 修改目标仓库；
* 发起网络请求；
* monkey-patch PRman 的决策代码；
* 无限阻塞进程；
* 在返回结果前伪造或破坏其他运行状态。

因此，后续的 digest、字段和概率校验只能防“坏输出”，完全防不了“坏代码”。这与 threat model 中把 scorer 视为不可信边界，以及 README 所称 helper 不修改目标仓库的表述并不相容。

本地 HTTP 模式虽然有进程边界，但也没有服务端认证或响应签名。服务只需回显 request digest；provider、model 和 calibrator 身份由客户端配置自行填入。任何能占用或劫持该 loopback 端口的本地进程都可以冒充评分器。Digest 证明的是“响应对应这个请求”，不是“响应来自这个模型”。

**修复方向：**把 Python entry-point 明确定义为“完全可信代码”，不要称其为不可信边界；生产评分器应放在受限子进程、容器或服务中，使用只读文件系统、清理后的环境变量、网络策略、CPU/内存/超时限制，并对 HTTP 响应做身份认证或签名。

## 2. 严重：证据没有与真实 diff、仓库和基线提交绑定

`candidate_id` 只被检查为一个 64 位小写十六进制字符串。核心引擎不会重新读取 diff，也不会验证这个摘要是否真的是当前工作区 diff 的 SHA-256。Gate 的 `evidence` 只要求是任意 JSON object，甚至空对象也能配合 `status: "pass"` 通过验证；评分 payload 除了 `criterion` 外也几乎没有强制结构。

所以系统无法识别这些情况：

* 测试针对旧 diff 运行，之后代码又被修改；
* 候选 A 的测试证据被拿去给候选 B 背书；
* `tests` gate 被标成 pass，但 evidence 是 `{}`；
* 同一个 diff 在不同仓库或不同 base commit 上被复用；
* compare 模式下，各候选实际上使用了不同的任务描述或仓库上下文。

项目的 threat model 已承认 helper 无法证明命令是否真的运行；这不是隐藏问题，但它直接削弱了“evidence-backed readiness”的核心产品价值。内容 digest 也不能解决真实性问题，因为不可信调用方可以修改内容后重新计算 digest。

**修复方向：**assessment 顶层应包含并绑定 `repository_id`、`base_commit`、规范化 diff 或 diff artifact digest、共享 task digest；测试证据应至少包含命令、退出码、执行时对应的候选摘要、时间、工具版本及日志摘要，并由受信任执行层生成而不是让调用方自由填写。

## 3. 严重：计算了 LCB，但单候选 `ready` 根本不看 LCB

代码计算：

$$
LCB = score - 0.75 \times uncertainty - truncation\_ratio
$$

但 `eligible` 判定仍然只检查原始 `score`、各 criterion minimum 和 uncertainty 上限；单候选模式随后直接把 `eligible` 变成 `ready`。LCB 只用于排序和 compare margin，没有作为绝对 readiness 门槛。

按照默认配置，可以构造：

* 六项 probability 都为 `0.75`；
* uncertainty 为 `0.12`；
* truncation ratio 为 `0.40`。

此时几何分数为 `0.75`，满足 `ready_score=0.72` 和所有 minimum；uncertainty 与 truncation 又恰好没有超过上限。因此会返回 `ready`。但：

$$
LCB = 0.75 - 0.75 \times 0.12 - 0.40 = 0.26
$$

也就是说，即使风险修正后的分数只有 **0.26**，系统仍然可以宣告 ready。这与项目突出宣传“uncertainty lower confidence bounds”的安全含义明显不一致。

**修复方向：**增加独立的 `ready_lcb_min` 并要求 `lcb >= ready_lcb_min`；或者直接用 LCB 而非 raw score 做 ready/revise 判定。若 LCB 只打算用于比较，应改名并在文档中明确，避免制造虚假的保守性印象。

## 4. 严重：compare 模式可以拿 OOD/abstain 候选当有效 runner-up

`aggregate()` 即使因为 OOD、过高 uncertainty 或严重 truncation 返回 `abstain`，仍然会附带非空 LCB。`finalize()` 又会把所有具有 LCB 的候选放进排名，而不是只排名“可比较”的候选。

例如：

* 候选 A：`eligible`，LCB `0.80`；
* 候选 B：`ood=true`，因此 provisional decision 是 `abstain`，但 LCB `0.10`。

`finalize()` 会认为有两个已评分候选，算出 margin `0.70`，然后把 A 判成 `ready`。问题在于 B 已经被评分器声明为分布外，A 与 B 的 margin 没有可信的比较意义。

此外还有两个 compare 缺陷：

* scorer metadata 只要求在**单次请求期间**稳定，没有在整个 assessment 中固定。一个 stateful scorer 可以对候选 A 使用 model revision A、对候选 B 使用 revision B，而最终结果仍只记录一个顶层 provider metadata。
* 当所有候选都只有 recoverable gate failure、没有 LCB 时，代码按候选 SHA 的字典序选择一个返回 `revise`。SHA 的字典序没有任何质量含义。

**修复方向：**一次 assessment 开始时固定 provider/model/calibrator metadata；compare 至少要求两个使用相同共享上下文、相同模型版本且非 OOD 的可比较候选；不要按哈希值选 revision candidate。

## 5. 中高：身份和未来结果泄漏过滤器很容易绕过

防泄漏逻辑是一个有限的字段名 denylist，只对规范化后的 key 做精确匹配。它会拦截 `author`、`merge_state` 等名字，但以下常见变体不会被拦截：

* `author_email`
* `reviewer`
* `reviewer_identity`
* `submitted_by`
* `review_decision`
* `merge_outcome`
* `final_status`
* `pr_conclusion`

把完整的 review 元数据 JSON 塞进一个普通字符串，同样不会被递归检查。另一方面，如果合法的结构化源码或配置中刚好含有 `author`、`merge` 等字段，又可能产生误报。

公开 scorer-request schema 进一步放大了这个问题：每个 criterion payload 只要求存在 `criterion`，其他字段任意，Schema 本身没有实施泄漏约束。

**修复方向：**不要用 denylist。应建立严格 allowlist，只从受信任 assessment context 中提取明确允许的 task、diff、repository rules 和 observed evidence 字段；对于文本型原始数据，也应明确其来源及敏感信息策略。

## 6. 中高：test-only scorer 并没有真正 fail closed

CLI 确实要求显式传入 `--allow-test-scorer`，但之后 fixture/static scorer 仍可以返回正式的：

```json
"selection": {"decision": "ready"}
```

只是旁边附加了 `"test_only": true`。仓库测试甚至明确断言 fixture demo 的 decision 应为 `ready`。任何只读取 `selection.decision`、忽略 `test_only` 的下游自动化都会把测试结果当成真实 readiness。

更严重的是，核心库的 `AssessmentEngine` 接受调用方自行传入的 `test_only: bool = False`，不会根据 scorer 类型推导。直接使用 Python API 时，可以把 `StaticScorer` 传给引擎而不设置 `test_only=True`，从而得到 `test_only:false` 的结果。

**修复方向：**trust classification 必须由 provider/registry 决定，不能由调用方提供；test scorer 的最终 decision 应强制为 `abstain`，或者使用独立状态如 `test_pass`，使错误消费结果变得困难。

## 7. 中等：公开 JSON Schema 与运行时合同不一致

仓库宣称有严格公共合同，但现有 Schema 可以接受运行时代码必然拒绝的对象：

* `assessment.schema.json` 允许 `mode:"single"` 时放两个或更多 candidate，运行时要求恰好一个；
* Schema 允许 `status:"pass"` 配合 `recoverable:true`，运行时拒绝；
* `score_bundle.schema.json` 只要求 scores 数组长度为 6，没有保证六个 criterion 唯一；六个 `correctness` 项可以通过 Schema，却会被运行时拒绝；
* `assessment_result.schema.json` 对每个 evaluation 只写了 `"type":"object"`，几乎不校验 gates、score bundle 和 aggregate 的输出结构。

CI 中所谓 schema 测试也只是调用 `json.loads()` 确认文件是合法 JSON，没有用 JSON Schema validator 验证示例，更没有做 Schema 与 Python parser 的一致性测试。

**修复方向：**加入 `jsonschema` 开发依赖；为每个 Schema 建立正反例；使用条件 Schema 约束 single/compare 数量；最好把 score 从数组改成以 criterion 为 key 的对象，以结构性保证唯一性。

## 8. 中等：gate 和决策配置存在语义漏洞

`required_gates` 只用于检查“哪些 gate 缺失”，但之后代码会对**所有提交的 gate**执行 unknown/failure 阻断。因此，一个本来只是作为补充信息加入的 `lint: unknown`，也会让整个 assessment abstain。当前设计没有“advisory gate”和“blocking gate”的区别。

另外：

* recoverable failure 不要求提供 actionable 建议，却仍然会返回 `revise`；
* 没有验证 `ready_score >= revise_floor`；
* 没有验证 ready uncertainty 阈值与 abstain uncertainty 阈值之间的合理关系；
* critical/soft minimum 可以都为空；
* weights、thresholds 与具体 scorer/model/calibrator 版本没有绑定。

因此，一个格式合法但语义矛盾的自定义配置仍可能运行，并产生难以解释的决策。Schema 同样没有这些跨字段约束。

## 9. 中等：评分器失败不会稳定地产生结构化 abstain

CLI 只捕获 `ContractError`。如果第三方 scorer：

* 抛出普通 `RuntimeError`；
* 返回 dict 而不是 `ScoreBundle`；
* metadata property 抛异常；
* 返回某些触发 `TypeError` 的畸形对象；
* 永久阻塞；

程序可能直接 traceback、崩溃或挂死，而不是返回规范化的 `scorer_unavailable`/`abstain` 结果。Python scorer 没有 timeout 或资源限制；输入 JSON 与 HTTP 请求体也没有大小上限，只有 HTTP **响应体**有 4 MiB 限制。

仓库路线图也把“provider failures produce a fail-closed handoff”列为未完成项，说明作者自己尚未把这条边界做完。

## 10. 产品本身还没有完成核心闭环

项目没有生产 scorer，阈值也是未经生产校准的 research defaults。默认真实运行只能返回 `abstain`；唯一能演示 `ready` 的是 fixture/static scorer。评分器 conformance suite、外部校准 scorer、证据完整性评估、全新 Codex 任务安装测试、Draft PR 确认路径都仍在路线图中。

所以当前它更准确的定位是：

> 一个定义了 readiness 合同和实验性聚合规则的框架，而不是已经能够可靠判断 PR 是否 ready 的工具。

## 发布与工程层面的明确问题

* **PyPI 名称已冲突。** `pyproject.toml` 使用 distribution name `prman`，但 PyPI 上已经存在一个同名、功能完全不同的 GitLab PR 工具。若发布 Python 包，会发生包名和 `prman` 命令冲突。建议把 distribution 改成 `prman-codex` 或类似名称。  ([PyPI][1])
* **当前 Plugin manifest 会卡在公共目录最终提交。** `shortDescription` 是 `Score and refine Codex code changes.`，共 36 个字符；当前最终目录规则要求不超过 30 个字符。包级校验可以允许更长，因此“结构 validator 通过”不代表可以正式发布。  ([ChatGPT Learn][2])
* **Python 兼容范围写得比 CI 实际验证范围更宽。** Metadata 是 `Python >=3.11`，但 CI 只跑 3.11 和 3.12；未来 Python 版本仍会被 pip 认为兼容。CI 也没有 wheel/sdist 构建安装测试、类型检查、Schema validator、覆盖率或 HTTP scorer 集成测试。
* **供应链和可复现性较弱。** GitHub Actions 使用 `actions/checkout@v4`、`setup-python@v5` 可变标签，`ubuntu-latest` 可变镜像，`setuptools>=68` 和 `ruff>=0.12,<1` 也没有 lock。
* **文档已经过期。** `IMPLEMENTATION_STATUS.md` 仍写着仓库可见性和许可证未决定、没有 Git remote；实际上仓库已经公开并采用 Apache-2.0。

## 建议的修复顺序

第一优先级应是**评分器隔离与认证、证据和 diff 的强绑定、LCB/compare 判定修正**；第二优先级是**test-only 核心强制、严格 allowlist payload、Schema/runtime 一致性和 scorer 失败结构化处理**；完成真实校准 scorer 与对抗性 false-ready 评估之后，才适合处理插件发布、PyPI 命名和 CI 加固。

在这些问题修复前，我不会把 PRman 的 `ready` 用作自动合并、发布或强制性 PR 准入依据。

[1]: https://pypi.org/project/prman/ "https://pypi.org/project/prman/"
[2]: https://learn.chatgpt.com/plugins/deploy/submission-errors "https://learn.chatgpt.com/plugins/deploy/submission-errors"
