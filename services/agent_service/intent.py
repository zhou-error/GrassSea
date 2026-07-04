"""意图识别模块

混合分类策略：
  1. 快速规则层（< 50ms）：关键词/正则匹配，覆盖 70% 常见意图
  2. LLM 语义层（200-500ms）：处理复杂/模糊意图
  3. 置信度阈值逻辑：> 0.85 直接路由，否则递升 LLM
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from shared.utils.config import Settings
from shared.utils.logging import get_logger

logger = get_logger(__name__)


class IntentType(str, Enum):
    CHITCHAT = "chitchat"
    KNOWLEDGE_QUERY = "knowledge_query"
    TOOL_CALL = "tool_call"
    PROFESSIONAL_TASK = "professional_task"
    SUB_AGENT_ORCHESTRATION = "sub_agent_orchestration"


@dataclass
class IntentResult:
    intent_type: IntentType
    confidence: float
    matched_rules: list[str] = field(default_factory=list)
    extracted_entities: dict = field(default_factory=dict)
    sub_intent: str | None = None


# ---- 规则引擎 ----

RULE_PATTERNS: dict[IntentType, list[tuple[str, float, list[str]]]] = {
    IntentType.CHITCHAT: [
        (r"^(你好|嗨|hello|hi|早上好|晚上好|下午好)[\s!！。.,，]*$", 0.95, ["greeting"]),
        (r"(谢谢|感谢|多谢|thank)", 0.95, ["thanks"]),
        (r"(再见|拜拜|bye|回头见)", 0.95, ["farewell"]),
        (r"(你是谁|你叫什么|介绍.*自己|你能做什么|功能|帮助|help)", 0.90, ["self_intro"]),
    ],
    IntentType.KNOWLEDGE_QUERY: [
        (r"(什么是|什么叫|何为|定义|解释|含义|概念)", 0.85, ["definition"]),
        (r"(规范|标准|要求|规定|条文|CCS|IMO|SOLAS|MARPOL|DNV|ABS|LR|BV)", 0.90, ["regulation"]),
        (r"(查|检索|搜索|查找|找一下|帮我找)", 0.80, ["search"]),
        (r"(为什么|原因|理由|原理)", 0.80, ["explanation"]),
        (r"(如何|怎么|怎样|方法|步骤|流程)", 0.80, ["howto"]),
        (r"(区别|对比|比较|差异|vs|和.*什么.*不同)", 0.80, ["compare"]),
        (r"(参数|尺寸|数据|指标|系数|数值)", 0.80, ["parameters"]),
    ],
    IntentType.TOOL_CALL: [
        (r"(生成|创建|制作|导出).*(报告|PDF|文档)", 0.90, ["report_gen"]),
        (r"(计算|求解|分析|模拟|仿真)", 0.85, ["computation"]),
        (r"(画|绘制|生成).*(图|型线|曲线|图纸)", 0.90, ["cad_draw"]),
        (r"(解析|读取|提取).*(文件|PDF|表格|Excel|型值表)", 0.85, ["file_parse"]),
        (r"(审查|检查|校验|验证|合规)", 0.85, ["compliance"]),
        (r"(上传|下载|导入|导出)", 0.80, ["file_ops"]),
        (r"(创建|添加|删除|更新).*(待办|任务|提醒)", 0.85, ["todo"]),
    ],
    IntentType.PROFESSIONAL_TASK: [
        (r"(稳性|完整稳性|破舱稳性|初稳性|大倾角稳性)", 0.92, ["stability"]),
        (r"(静水力|排水量|浮心|稳心|邦戎曲线|静水力曲线)", 0.92, ["hydrostatics"]),
        (r"(阻力|快速性|推进|螺旋桨|Holtrop|ITTC)", 0.90, ["resistance"]),
        (r"(型线|型值|船型|线型|光顺|型线图|型值表)", 0.92, ["hull_design"]),
        (r"(船型改造|母型船|变换|优化设计)", 0.88, ["hull_transform"]),
        (r"(结构|强度|舱壁|肋骨|桁材|甲板|船壳)", 0.85, ["structure"]),
        (r"(管系|管路|系统|舱室|布置)", 0.80, ["outfitting"]),
    ],
    IntentType.SUB_AGENT_ORCHESTRATION: [
        (r"(联合|协同|多.*一起|同时.*和|既.*又.*还|全部|完整.*流程)", 0.85, ["multi_task"]),
        (r"(从.*到.*整个|全流程|全生命周期|端到端)", 0.85, ["full_pipeline"]),
        (r"(设计.*方案|多方案|比选|优化.*方案)", 0.80, ["multi_design"]),
    ],
}


class IntentClassifier:
    """意图分类器（规则引擎 + LLM）"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.confidence_threshold = 0.85

    async def initialize(self) -> None:
        logger.info("Intent classifier initialized", threshold=self.confidence_threshold)

    async def classify(self, text: str) -> IntentResult:
        """分类用户意图"""
        # 1. 规则引擎匹配
        rule_result = self._rule_match(text)

        # 2. 置信度判断
        if rule_result and rule_result.confidence >= self.confidence_threshold:
            logger.debug("Rule matched", intent=rule_result.intent_type, confidence=rule_result.confidence)
            return rule_result

        # 3. 递升到 LLM 分类
        llm_result = await self._llm_classify(text)
        if llm_result:
            return llm_result

        # 4. 兜底：默认为闲聊
        if rule_result:
            return rule_result
        return IntentResult(intent_type=IntentType.CHITCHAT, confidence=0.5)

    def _rule_match(self, text: str) -> IntentResult | None:
        """规则引擎匹配"""
        best_intent = None
        best_confidence = 0.0
        best_rules = []

        for intent_type, patterns in RULE_PATTERNS.items():
            for pattern, confidence, rules in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_intent = intent_type
                        best_rules = rules

        if best_intent:
            entities = self._extract_entities(text)
            return IntentResult(
                intent_type=best_intent,
                confidence=best_confidence,
                matched_rules=best_rules,
                extracted_entities=entities,
            )
        return None

    def _extract_entities(self, text: str) -> dict:
        """提取实体（船型、规范、参数等）"""
        entities = {}

        # 船型
        ship_types = ["散货船", "油船", "集装箱船", "客船", "工程船", "军舰", "LNG船", "LPG船", "滚装船", "渡船", "拖船", "驳船"]
        for st in ship_types:
            if st in text:
                entities["ship_type"] = st
                break

        # 规范
        regulations = ["CCS", "DNV", "ABS", "LR", "BV", "IMO", "SOLAS", "MARPOL", "ISO"]
        for reg in regulations:
            if reg.lower() in text.lower():
                entities.setdefault("regulations", []).append(reg)

        # 参数
        param_match = re.findall(r"(船长|型宽|型深|吃水|排水量|方型系数|棱形系数|水线面系数|航速|载重量)", text)
        if param_match:
            entities["parameters"] = param_match

        return entities

    async def _llm_classify(self, text: str) -> IntentResult | None:
        """LLM 语义分类"""
        if not self.settings.DEEPSEEK_API_KEY:
            return None

        prompt = f"""请对以下用户输入进行意图分类，返回 JSON 格式。

意图类型:
- chitchat: 闲聊/寒暄/自我介绍
- knowledge_query: 知识查询/规范检索/术语解释
- tool_call: 工具调用/报告生成/文件操作
- professional_task: 专业任务/稳性计算/型线设计
- sub_agent_orchestration: 多智能体协同/全流程设计

用户输入: {text}

请返回 JSON: {{"intent": "<意图类型>", "confidence": <0.0-1.0>, "reason": "<简短理由>"}}"""

        try:
            import httpx
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self.settings.DEEPSEEK_BASE_URL}/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.settings.DEEPSEEK_API_KEY}"},
                    json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "max_tokens": 200, "temperature": 0.1},
                )
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                import json
                result = json.loads(content)
                intent_type = IntentType(result.get("intent", "chitchat"))
                return IntentResult(intent_type=intent_type, confidence=result.get("confidence", 0.7))
        except Exception as e:
            logger.warning("LLM intent classification failed", error=str(e))
            return None
