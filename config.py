"""集中配置：固定标签表、模型、成本护栏、Notion ID。"""

# 精读用模型（质量优先）
MODEL = "claude-opus-4-8"

# 成本护栏：预估费用超过此值（美元）先请用户确认
COST_ALERT_USD = 10.0

# Opus 4.8 报价（美元 / 百万 token）
PRICE_INPUT_PER_M = 5.0
PRICE_OUTPUT_PER_M = 25.0

# 章节切分失败时的兜底：按字数硬切
HARD_SPLIT_CHARS = 8000

# 每章精读的输出上限（token；含 adaptive thinking，需留足余量）
MAX_TOKENS_PER_CHAPTER = 16000
# 合成总览的输出上限（token）
MAX_TOKENS_SYNTHESIS = 16000

# 固定主题标签表（用户可增删；AI 只能从中选取）
FIXED_TAGS = [
    "估值",
    "风险控制",
    "仓位管理",
    "市场心理",
    "择时",
    "财报分析",
    "资产配置",
    "安全边际",
    "复利",
    "分散化",
    "护城河/竞争优势",
    "宏观周期",
    "交易成本/税费",
    "投资纪律",
]

# 每日软配额：默认原则课条数
DAILY_LESSON_LIMIT = 5

# 可执行度取值
ACTIONABILITY_VALUES = ["原则", "可直接执行", "需自己判断"]

# Notion 目标（从 .env 读取；此处仅占位说明，运行时由 read_book.py 注入）
# NOTION_OVERVIEW_PARENT_PAGE_ID / NOTION_OPINIONS_DATABASE_ID
