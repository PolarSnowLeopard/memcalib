#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = SCRIPT_DIR / "data" / "memory_abc_coherent_100.jsonl"
DEFAULT_SUMMARY = SCRIPT_DIR / "data" / "memory_abc_coherent_100.summary.json"
DEFAULT_HTML = SCRIPT_DIR / "data" / "memory_abc_coherent_100.html"

LABEL_TO_RELATION = {
    "A": "non_applicable",
    "B": "auxiliary",
    "C": "necessary",
}


SCENARIOS: list[dict[str, Any]] = [
    {
        "theme": "travel_day_plan",
        "domain": "travel",
        "task_type": "planning",
        "query": "帮我安排这个周末在{city}的一日{focus}路线。",
        "memory_intro": "我这次在{city}旅行时给自己记了几条状态：",
        "choices": {
            "city": ["东京", "京都", "成都", "杭州", "首尔", "台北", "上海", "曼谷"],
            "focus": ["餐饮和散步", "博物馆和咖啡", "老街闲逛", "亲子游", "雨天室内活动", "轻松拍照"],
            "c": ["我的膝盖最近不太舒服，连续步行最好不要超过五公里", "我对花生严重过敏，吃饭时必须避开花生和花生酱", "我晚上九点前必须回酒店参加远程会议", "我这次预算比较紧，一天餐饮和门票最好控制在300元以内"],
            "b1": ["我更喜欢安静的小店，不太想排很长的网红队", "我喜欢把路线安排得松一点，中间留出休息时间", "我更喜欢本地生活感强的地方，而不是大型商业街", "我拍照时更喜欢自然光和人少的街区"],
            "b2": ["我通常早上精神最好，复杂一点的活动适合放上午", "我不太喜欢频繁换乘，能少换交通工具更好", "我午饭后容易犯困，下午适合安排轻量活动", "我更愿意把预算花在体验上，而不是纪念品上"],
            "a": ["我已经买好了明信片邮票", "我手机壳是蓝色的", "我上次旅行时住过一家很吵的民宿", "我喜欢收集地铁票根"],
        },
        "atoms": [
            ("C", "constraint", "hard travel constraint", "{c}", "该信息直接限制路线、餐饮、预算或时间安排，忽略会使计划不可执行或不安全。"),
            ("B", "preference", "soft routing preference", "{b1}", "该信息能改善路线贴合度，但不是完成一日路线的必要条件。"),
            ("B", "preference", "soft scheduling preference", "{b2}", "该信息影响排序和节奏安排，但不决定核心可行性。"),
            ("A", "episodic_fact", "same-trip adjacent but irrelevant", "{a}", "该信息与旅行主题相邻，但对当前路线规划没有规范性作用，使用会造成过度结合。"),
        ],
    },
    {
        "theme": "meal_planning",
        "domain": "daily_life",
        "task_type": "recommendation",
        "query": "帮我设计三天{meal_type}菜单。",
        "memory_intro": "我最近在整理自己的饮食习惯：",
        "choices": {
            "meal_type": ["高蛋白晚餐", "工作日便当", "低负担晚餐", "周末早午餐", "素食晚餐", "家庭聚餐"],
            "c": ["我不吃牛肉，也不希望菜单里出现牛肉替代品", "我对虾和蟹过敏，不能安排任何甲壳类海鲜", "我家里没有烤箱，只能用炉灶和空气炸锅", "我工作日晚饭最多只能做三十分钟"],
            "b1": ["我最近在做力量训练，希望蛋白质稍微高一点", "我更喜欢清淡口味，不太能吃辣", "我喜欢一次多做一点，第二天可以带饭", "我希望食材尽量在普通超市买得到"],
            "b2": ["我不介意重复使用同一种主食", "我喜欢菜谱步骤写得具体一点", "我周三晚上通常比较累，适合最简单的一餐", "我喜欢把蔬菜做得脆一点"],
            "a": ["我收藏了一口蓝色铸铁锅", "我上个月看过一部美食纪录片", "我喜欢把冰箱贴按城市分类", "我厨房窗帘是绿色的"],
        },
        "atoms": [
            ("C", "constraint", "dietary or cooking constraint", "{c}", "该信息决定菜单可行性或安全性，必须被遵守。"),
            ("B", "preference", "nutrition or taste preference", "{b1}", "该信息影响菜单风格和排序，但不单独决定菜单正确性。"),
            ("B", "format_preference", "execution preference", "{b2}", "该信息帮助提高菜单实用性，但不是硬约束。"),
            ("A", "profile_fact", "kitchen-adjacent irrelevant detail", "{a}", "该信息与厨房或饮食主题相邻，但不应影响菜单内容。"),
        ],
    },
    {
        "theme": "book_recommendation",
        "domain": "entertainment",
        "task_type": "recommendation",
        "query": "推荐五本适合我最近读的{genre}书。",
        "memory_intro": "我最近给自己的阅读状态做了备注：",
        "choices": {
            "genre": ["科幻小说", "推理小说", "非虚构作品", "历史小说", "轻松文学", "商业传记"],
            "c": ["我不想看结局特别压抑的书", "我最近只想读中文译本或中文原著", "我已经读过《三体》和《沙丘》，这次不要重复推荐", "我希望每本书单册篇幅不要超过三百页"],
            "b1": ["我喜欢节奏快、章节短的书", "我喜欢人物关系清楚、设定不要太绕的书", "我更在意阅读体验，不追求经典地位", "我喜欢有明确悬念推进的叙事"],
            "b2": ["我通常只在通勤时读书，适合碎片化阅读", "我喜欢推荐理由写得克制一点，不要剧透", "我更愿意先读一本入门友好的作品", "我喜欢每本书附一句适合我的理由"],
            "a": ["我收藏的是纸质精装版比较多", "我的书架按颜色排列", "我去年买过一盏阅读灯", "我常用的书签是金属材质"],
        },
        "atoms": [
            ("C", "constraint", "reading selection constraint", "{c}", "该信息直接限制推荐范围，忽略会产生不符合要求的书单。"),
            ("B", "preference", "reading taste", "{b1}", "该信息改善推荐匹配度，但不是硬性筛选条件。"),
            ("B", "format_preference", "recommendation style", "{b2}", "该信息影响推荐说明方式或排序。"),
            ("A", "profile_fact", "book-adjacent irrelevant detail", "{a}", "该信息与阅读生活相关，但不应影响书名选择。"),
        ],
    },
    {
        "theme": "coding_explanation",
        "domain": "coding",
        "task_type": "qa",
        "query": "给我解释{topic}，最好带一个小例子。",
        "memory_intro": "我记录过自己的编程学习状态：",
        "choices": {
            "topic": ["二叉搜索树删除操作", "动态规划里的状态转移", "Python 装饰器", "数据库索引为什么能加速查询", "异步编程的事件循环", "哈希表冲突处理"],
            "c": ["我目前主要用 Python，不熟悉 C++ 语法", "我明确想避免递归实现，优先理解迭代写法", "我刚开始学这块内容，不能默认我知道复杂数学符号", "我需要面向面试回答，解释要覆盖时间复杂度"],
            "b1": ["我喜欢先看直观类比，再看代码", "我对图示化解释接受度比较高", "我更容易理解逐步 dry run 的例子", "我喜欢先知道常见坑，再看完整流程"],
            "b2": ["我通常一次只消化一个核心概念", "我喜欢变量名取得有语义一点", "我希望例子规模小，不要一上来太复杂", "我喜欢最后有三句话总结"],
            "a": ["我最近在做一个数据库课程项目", "我的编辑器主题是深色", "我上周刚换了机械键盘", "我习惯把代码文件放在桌面"],
        },
        "atoms": [
            ("C", "skill_level", "technical constraint", "{c}", "该信息决定解释语言、实现方式或覆盖范围，忽略会降低回答正确性。"),
            ("B", "format_preference", "learning style", "{b1}", "该信息帮助选择解释路径，但不是答案成立的必要条件。"),
            ("B", "format_preference", "example style", "{b2}", "该信息影响示例组织方式。"),
            ("A", "profile_fact", "coding-adjacent irrelevant detail", "{a}", "该信息与编程场景相邻，但不应改变概念解释。"),
        ],
    },
    {
        "theme": "work_email",
        "domain": "work",
        "task_type": "writing",
        "query": "帮我写一封{email_type}邮件。",
        "memory_intro": "我对工作沟通有这些偏好和背景：",
        "choices": {
            "email_type": ["给导师申请延期", "向客户解释项目延迟", "请同事补充材料", "向主管申请调休", "拒绝一个不合适的会议邀请", "跟进迟迟没有回复的合作方"],
            "c": ["我不想透露家庭原因的具体细节", "这封邮件必须控制在两百字以内", "我需要语气明确，但不能承诺具体完成日期", "我不能提到内部预算问题"],
            "b1": ["我希望语气诚恳，但不要过度道歉", "对方更喜欢直接看结论", "我平时不喜欢使用太夸张的客套话", "我希望保留一点协商空间"],
            "b2": ["我喜欢邮件开头先说明目的", "我更希望结尾给出下一步动作", "我倾向用简洁标题", "我希望正文分两小段"],
            "a": ["我常用的笔记软件是深色模式", "我办公桌上有一个白色台历", "我喜欢把会议记录按月份归档", "我昨天整理了邮箱标签"],
        },
        "atoms": [
            ("C", "constraint", "disclosure or length constraint", "{c}", "该信息直接限制邮件内容，忽略会违反用户要求。"),
            ("B", "preference", "tone preference", "{b1}", "该信息影响语气和表达强度。"),
            ("B", "format_preference", "email structure preference", "{b2}", "该信息影响邮件结构。"),
            ("A", "profile_fact", "work-adjacent irrelevant detail", "{a}", "该信息与工作环境相邻，但不应进入邮件内容。"),
        ],
    },
    {
        "theme": "study_plan",
        "domain": "education",
        "task_type": "planning",
        "query": "帮我制定一个{duration}的{subject}复习计划。",
        "memory_intro": "我最近的学习状态是这样的：",
        "choices": {
            "duration": ["两周", "十天", "一个月", "七天", "三周", "五天"],
            "subject": ["机器学习", "线性代数", "英语六级", "产品经理面试", "数据结构", "统计学"],
            "c": ["我每天只有晚上八点以后有空", "我周末两天都要上班，只能安排轻量任务", "我基础很薄弱，需要从入门知识开始", "我考试前一天不能熬夜"],
            "b1": ["我喜欢视频课和练习题结合", "我更容易被明确的小目标推动", "我希望每天都有可勾选的任务", "我喜欢先复习框架，再做题"],
            "b2": ["我早上通勤时可以听音频", "我注意力一般只能连续集中四十分钟", "我喜欢每三天做一次回顾", "我希望计划里留出缓冲时间"],
            "a": ["我上个月买了降噪耳机", "我的书桌靠窗", "我习惯用蓝色荧光笔", "我收藏了很多空白笔记本"],
        },
        "atoms": [
            ("C", "constraint", "availability or baseline constraint", "{c}", "该信息决定计划强度、起点或时间安排。"),
            ("B", "preference", "learning preference", "{b1}", "该信息改善学习计划的适配度。"),
            ("B", "format_preference", "study rhythm preference", "{b2}", "该信息影响节奏和复习方式。"),
            ("A", "profile_fact", "study-adjacent irrelevant detail", "{a}", "该信息与学习环境相邻，但不应决定复习计划。"),
        ],
    },
    {
        "theme": "shopping_bag",
        "domain": "shopping",
        "task_type": "recommendation",
        "query": "帮我挑一个适合{use_case}的双肩包。",
        "memory_intro": "我之前记录过自己买包时会考虑这些事：",
        "choices": {
            "use_case": ["通勤", "短途出差", "大学上课", "带娃出门", "健身房和上班两用", "周末城市徒步"],
            "c": ["我每天都要带一台14寸电脑", "我肩颈容易酸，不能选自重太重的包", "我经常下雨天骑车，需要基础防水", "我必须能放下A4文件夹"],
            "b1": ["我喜欢外观极简，不想要太多外露口袋", "我更喜欢能直立放在地上的款式", "我希望内部隔层清楚一点", "我偏好黑色或深灰色"],
            "b2": ["我通常会带水杯和折叠伞", "我不太喜欢明显的品牌 logo", "我希望肩带不要太硬", "我喜欢开合方式简单一点"],
            "a": ["我的手机是蓝色的", "我上一个钱包是棕色皮质", "我喜欢收集帆布袋", "我电脑桌面壁纸是山景"],
        },
        "atoms": [
            ("C", "constraint", "capacity or ergonomic constraint", "{c}", "该信息是选包硬约束，忽略会推荐不可用产品。"),
            ("B", "preference", "style preference", "{b1}", "该信息影响款式排序。"),
            ("B", "preference", "usage detail", "{b2}", "该信息帮助筛选更合适的功能。"),
            ("A", "profile_fact", "accessory-adjacent irrelevant detail", "{a}", "该信息与个人物品相关，但不应影响背包选择。"),
        ],
    },
    {
        "theme": "fitness_plan",
        "domain": "fitness",
        "task_type": "planning",
        "query": "帮我安排一周{fitness_goal}计划。",
        "memory_intro": "我最近关于运动的记录是：",
        "choices": {
            "fitness_goal": ["入门跑步", "恢复体能", "居家力量训练", "减脂运动", "晨练", "低冲击训练"],
            "c": ["我膝盖有旧伤，不能安排高冲击跳跃", "我只有每天早上三十分钟可以运动", "我医生建议最近避免大重量深蹲", "我刚开始运动，连续跑步不能超过十分钟"],
            "b1": ["我更喜欢户外运动", "我需要计划里写清楚热身和拉伸", "我喜欢用可量化的小目标", "我比较容易因为动作太复杂而放弃"],
            "b2": ["我家附近有一圈400米的操场", "我有一副轻哑铃", "我希望每周至少留一天完全休息", "我喜欢把训练安排在固定时间"],
            "a": ["我的瑜伽垫是紫色的", "我去年买过一个运动水壶", "我常看的运动博主住在上海", "我喜欢用绿色的运动记录表"],
        },
        "atoms": [
            ("C", "safety_sensitive", "injury or time constraint", "{c}", "该信息直接影响运动安全或可执行性。"),
            ("B", "preference", "exercise preference", "{b1}", "该信息改善计划坚持度。"),
            ("B", "profile_fact", "available equipment or location", "{b2}", "该信息影响具体动作和场地选择。"),
            ("A", "profile_fact", "fitness-adjacent irrelevant detail", "{a}", "该信息与运动生活相关，但不应影响训练处方。"),
        ],
    },
    {
        "theme": "home_cleaning",
        "domain": "daily_life",
        "task_type": "planning",
        "query": "帮我规划一个{home_task}的顺序。",
        "memory_intro": "我关于家务和居住状态有这些记录：",
        "choices": {
            "home_task": ["周末大扫除", "搬家前整理", "客人来访前清洁", "小户型收纳", "厨房深度清洁", "阳台整理"],
            "c": ["我对灰尘过敏，清洁时需要尽量减少扬尘", "我家有一只猫，清洁用品不能对宠物有刺激性", "我腰不太好，不能安排长时间弯腰搬重物", "我只有两个小时，必须优先处理最影响观感的区域"],
            "b1": ["我喜欢先做能立刻看到效果的任务", "我希望把噪音大的步骤放在白天", "我不喜欢同时打开太多收纳箱", "我希望按房间分阶段完成"],
            "b2": ["我家阳台通风最好", "我厨房台面东西比较多", "我客厅是访客最先看到的地方", "我希望最后留十五分钟检查遗漏"],
            "a": ["厨房水槽上个月刚疏通过", "我买过一套同色衣架", "我喜欢香薰蜡烛的玻璃罐", "我冰箱贴来自不同城市"],
        },
        "atoms": [
            ("C", "constraint", "health or time constraint", "{c}", "该信息决定清洁方式、优先级或安全边界。"),
            ("B", "preference", "workflow preference", "{b1}", "该信息影响顺序和执行体验。"),
            ("B", "profile_fact", "home layout detail", "{b2}", "该信息帮助安排具体步骤。"),
            ("A", "episodic_fact", "home-adjacent irrelevant detail", "{a}", "该信息与家居相关，但不应影响本次任务顺序。"),
        ],
    },
    {
        "theme": "language_learning",
        "domain": "education",
        "task_type": "planning",
        "query": "帮我制定一个{duration}的{language}入门计划。",
        "memory_intro": "我记录过自己的语言学习情况：",
        "choices": {
            "duration": ["30天", "两周", "一个月", "十天", "六周", "三周"],
            "language": ["日语", "法语", "西班牙语", "德语", "韩语", "意大利语"],
            "c": ["我已经掌握最基础的发音规则，不想从字母表重新开始", "我每天最多只能学二十分钟", "我主要目标是旅行口语，不准备考试", "我完全零基础，需要从最基本的问候和发音开始"],
            "b1": ["我喜欢用游戏化打卡保持动力", "我更喜欢先学高频表达", "我希望每天都有一句可以直接使用的话", "我喜欢把听力和跟读结合"],
            "b2": ["我每天通勤大约四十分钟，可以听音频", "我周末时间比较完整，可以安排复盘", "我喜欢用表格记录进度", "我希望计划不要太密集"],
            "a": ["我最近在看韩国综艺", "我手机输入法里有很多表情包", "我收藏过几张旅行地图", "我喜欢把课程图标放在主屏幕第一页"],
        },
        "atoms": [
            ("C", "skill_level", "baseline or goal constraint", "{c}", "该信息决定课程起点和目标，忽略会使计划不适配。"),
            ("B", "preference", "learning style", "{b1}", "该信息提高计划执行性。"),
            ("B", "profile_fact", "available study context", "{b2}", "该信息影响学习任务安排。"),
            ("A", "profile_fact", "language-adjacent irrelevant detail", "{a}", "该信息与语言文化或手机使用相邻，但不应影响学习计划。"),
        ],
    },
    {
        "theme": "event_planning",
        "domain": "daily_life",
        "task_type": "planning",
        "query": "帮我安排一个{event_type}的流程。",
        "memory_intro": "我之前记录过办活动时的一些情况：",
        "choices": {
            "event_type": ["小型生日聚会", "读书会", "团队破冰活动", "家庭晚餐", "线上分享会", "朋友桌游夜"],
            "c": ["参与者里有人不吃猪肉，餐食必须避开", "活动总时长不能超过两小时", "场地晚上十点必须关闭", "预算上限是800元"],
            "b1": ["我不喜欢太吵的环节", "我希望流程自然一点，不要太像正式会议", "我喜欢把互动安排得轻松一点", "我希望给迟到的人留一点缓冲"],
            "b2": ["我更愿意把重点放在聊天和体验上", "我希望开场不要太尴尬", "我喜欢准备一个简单的备用方案", "我倾向把合照放在最后"],
            "a": ["我喜欢蓝色邀请函", "我家里有一串旧彩灯", "我上次活动剩了一包纸杯", "我喜欢把嘉宾名单存在表格里"],
        },
        "atoms": [
            ("C", "constraint", "event hard constraint", "{c}", "该信息决定流程、餐食、时间或预算边界。"),
            ("B", "preference", "event style preference", "{b1}", "该信息影响活动风格。"),
            ("B", "preference", "flow preference", "{b2}", "该信息影响环节排序。"),
            ("A", "profile_fact", "event-adjacent irrelevant detail", "{a}", "该信息与办活动相邻，但不应决定流程。"),
        ],
    },
    {
        "theme": "weekly_report",
        "domain": "work",
        "task_type": "writing",
        "query": "帮我设计一个{report_type}的结构。",
        "memory_intro": "我关于汇报和数据沟通有这些记录：",
        "choices": {
            "report_type": ["销售周报", "产品实验复盘", "用户增长周报", "客服问题月报", "项目进展汇报", "运营日报"],
            "c": ["老板只看一页摘要，所以结构必须能压缩到一页", "这次汇报不能展示单个客户名称", "团队要求所有指标都要有环比", "结论必须先于数据细节出现"],
            "b1": ["团队习惯按区域看数据", "我希望先讲异常，再讲常规指标", "听众更关心下一步动作", "我希望减少长段文字"],
            "b2": ["我喜欢每个部分都有一句 takeaway", "我希望图表数量控制在三个以内", "我倾向把风险单独列出来", "我喜欢用问题-发现-动作的顺序"],
            "a": ["我喜欢深色主题的幻灯片", "我上季度换过一次CRM头像", "我收藏了很多图表配色方案", "我常用的会议室在12楼"],
        },
        "atoms": [
            ("C", "constraint", "reporting hard constraint", "{c}", "该信息决定报告结构是否合格。"),
            ("B", "preference", "audience or analysis preference", "{b1}", "该信息影响结构排序和表达重点。"),
            ("B", "format_preference", "report style preference", "{b2}", "该信息改善汇报可读性。"),
            ("A", "profile_fact", "report-adjacent irrelevant detail", "{a}", "该信息与汇报工作相邻，但不应影响结构设计。"),
        ],
    },
]


def choose(options: list[str], index: int, offset: int = 0) -> str:
    return options[(index + offset) % len(options)]


def fill_template(text: str, values: dict[str, str]) -> str:
    return text.format(**values)


def generate_sample(index: int) -> dict[str, Any]:
    scenario = SCENARIOS[index % len(SCENARIOS)]
    variant = index // len(SCENARIOS)
    values = {}
    for key, options in scenario["choices"].items():
        values[key] = choose(options, variant, offset=index % 3)

    sample_id = f"cohmem_{index + 1:06d}"
    atoms = []
    atom_sentences = []
    for atom_index, (label, atom_type, role, atom_template, rationale_template) in enumerate(scenario["atoms"], start=1):
        atom_text = fill_template(atom_template, values)
        atom_sentences.append(atom_text)
        atoms.append(
            {
                "atom_id": f"{sample_id}_atom_{atom_index:02d}",
                "atom_text": atom_text,
                "atom_type": atom_type,
                "label": label,
                "relation": LABEL_TO_RELATION[label],
                "coherence_role": role,
                "theme": scenario["theme"],
                "rationale": fill_template(rationale_template, values),
            }
        )

    label_counts = dict(sorted(Counter(atom["label"] for atom in atoms).items()))
    return {
        "sample_id": sample_id,
        "query": fill_template(scenario["query"], values),
        "memory_block": f"{fill_template(scenario['memory_intro'], values)}" + "；".join(atom_sentences) + "。",
        "memory_block_theme": scenario["theme"],
        "domain": scenario["domain"],
        "task_type": scenario["task_type"],
        "atoms": atoms,
        "block_composition": {
            "atom_count": len(atoms),
            "label_counts": label_counts,
            "mixed_label": len(label_counts) > 1,
        },
        "diagnostic_tags": ["coherent_mixed_block", "non_overlap_main_candidate", "template_seed"],
        "prototype_notes": "Controlled coherent seed; atoms are intentionally theme-consistent and labels are assigned at atom-query level.",
    }


def generate_samples(limit: int) -> list[dict[str, Any]]:
    return [generate_sample(index) for index in range(limit)]


def summarize(samples: list[dict[str, Any]]) -> dict[str, Any]:
    label_counts: Counter = Counter()
    relation_counts: Counter = Counter()
    atom_type_counts: Counter = Counter()
    theme_counts: Counter = Counter()
    domain_counts: Counter = Counter()
    task_counts: Counter = Counter()
    atom_count = 0
    for sample in samples:
        atom_count += len(sample["atoms"])
        theme_counts[sample["memory_block_theme"]] += 1
        domain_counts[sample["domain"]] += 1
        task_counts[sample["task_type"]] += 1
        for atom in sample["atoms"]:
            label_counts[atom["label"]] += 1
            relation_counts[atom["relation"]] += 1
            atom_type_counts[atom["atom_type"]] += 1
    return {
        "total_samples": len(samples),
        "total_atoms": atom_count,
        "avg_atoms_per_sample": atom_count / len(samples) if samples else 0,
        "label_counts": dict(sorted(label_counts.items())),
        "relation_counts": dict(sorted(relation_counts.items())),
        "atom_type_counts": dict(sorted(atom_type_counts.items())),
        "theme_counts": dict(sorted(theme_counts.items())),
        "domain_counts": dict(sorted(domain_counts.items())),
        "task_type_counts": dict(sorted(task_counts.items())),
        "prototype_limitations": [
            "This is a controlled seed set for judging benchmark framing, not final naturalistic data.",
            "Memory blocks are template-written to enforce coherence.",
            "Overlap and conflict subsets are still excluded from this main-candidate prototype.",
        ],
    }


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_html(samples: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    cards = []
    for sample in samples:
        atom_rows = []
        for atom in sample["atoms"]:
            atom_rows.append(
                f"""
                <tr>
                  <td><span class="label label-{html.escape(atom['label'])}">{html.escape(atom['label'])}</span></td>
                  <td>{html.escape(atom['relation'])}</td>
                  <td>{html.escape(atom['atom_type'])}</td>
                  <td>{html.escape(atom['coherence_role'])}</td>
                  <td>{html.escape(atom['atom_text'])}</td>
                  <td>{html.escape(atom['rationale'])}</td>
                </tr>
                """
            )
        cards.append(
            f"""
            <article class="sample">
              <div class="sample-head">
                <div>
                  <h2>{html.escape(sample['sample_id'])}</h2>
                  <p>{html.escape(sample['memory_block_theme'])} · {html.escape(sample['domain'])} · {html.escape(sample['task_type'])}</p>
                </div>
                <span class="tag">coherent mixed block</span>
              </div>
              <section>
                <h3>Query</h3>
                <p class="query">{html.escape(sample['query'])}</p>
              </section>
              <section>
                <h3>Memory block</h3>
                <p>{html.escape(sample['memory_block'])}</p>
              </section>
              <section>
                <h3>Atomic memory labels</h3>
                <table>
                  <thead><tr><th>Label</th><th>Relation</th><th>Type</th><th>Role</th><th>Atom</th><th>Rationale</th></tr></thead>
                  <tbody>{''.join(atom_rows)}</tbody>
                </table>
              </section>
            </article>
            """
        )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Coherent Memory ABC Seed 100</title>
  <style>
    :root {{
      --paper: #f7f9fb;
      --ink: #18212f;
      --muted: #647084;
      --line: #d8dee8;
      --a: #6c7888;
      --b: #1f6f8b;
      --c: #9a3b2f;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--paper);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.62;
      letter-spacing: 0;
    }}
    header {{
      padding: 34px min(5vw, 60px) 22px;
      background: #fff;
      border-bottom: 1px solid var(--line);
    }}
    header h1 {{ margin: 0; font-size: clamp(30px, 5vw, 54px); line-height: 1; }}
    header p {{ max-width: 920px; margin: 14px 0 0; color: #3c4858; font-size: 17px; }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      padding: 18px min(5vw, 60px);
    }}
    .metric, .sample {{
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 14px 34px rgba(24, 33, 47, 0.07);
    }}
    .metric {{ padding: 13px 15px; }}
    .metric strong {{ display: block; font-size: 24px; }}
    .metric span {{ color: var(--muted); font-size: 13px; }}
    main {{ display: grid; gap: 16px; padding: 10px min(5vw, 60px) 60px; }}
    .sample {{ overflow: hidden; }}
    .sample-head {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      padding: 15px 17px;
      border-bottom: 1px solid var(--line);
      background: #fbfcfe;
    }}
    .sample h2 {{ margin: 0; font-size: 18px; }}
    .sample-head p {{ margin: 3px 0 0; color: var(--muted); font-size: 13px; }}
    .tag {{
      display: inline-flex;
      align-items: center;
      height: 26px;
      padding: 0 9px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: #eef3f8;
      color: #344054;
      font-size: 12px;
      font-weight: 760;
    }}
    section {{ padding: 13px 17px; border-bottom: 1px solid var(--line); }}
    section:last-child {{ border-bottom: 0; }}
    h3 {{ margin: 0 0 7px; font-size: 13px; text-transform: uppercase; color: var(--muted); letter-spacing: 0.04em; }}
    p {{ margin: 0; }}
    .query {{ font-size: 18px; font-weight: 720; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 9px 8px; border-top: 1px solid var(--line); vertical-align: top; text-align: left; }}
    th {{ color: #344054; background: #f4f7fa; }}
    .label {{
      display: inline-grid;
      place-items: center;
      width: 28px;
      height: 28px;
      color: white;
      border-radius: 50%;
      font-weight: 900;
    }}
    .label-A {{ background: var(--a); }}
    .label-B {{ background: var(--b); }}
    .label-C {{ background: var(--c); }}
    @media (max-width: 900px) {{
      .summary {{ grid-template-columns: 1fr 1fr; }}
      .sample-head {{ flex-direction: column; }}
      table {{ display: block; overflow-x: auto; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Coherent Memory ABC Seed 100</h1>
    <p>Controlled seed set where each memory block contains multiple atom-level facts from the same user situation. This version is for judging whether the benchmark framing feels natural enough before adding external sources and model-assisted decomposition.</p>
  </header>
  <div class="summary">
    <div class="metric"><strong>{summary['total_samples']}</strong><span>samples</span></div>
    <div class="metric"><strong>{summary['total_atoms']}</strong><span>atomic memories</span></div>
    <div class="metric"><strong>{summary['label_counts'].get('A', 0)}</strong><span>A atoms</span></div>
    <div class="metric"><strong>{summary['label_counts'].get('C', 0)}</strong><span>C atoms</span></div>
  </div>
  <main>{''.join(cards)}</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build coherent non-atomic Memory ABC seed samples.")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--html", type=Path, default=DEFAULT_HTML)
    args = parser.parse_args()

    samples = generate_samples(args.limit)
    summary = summarize(samples)
    write_jsonl(args.output, samples)
    write_json(args.summary, summary)
    args.html.parent.mkdir(parents=True, exist_ok=True)
    args.html.write_text(build_html(samples, summary), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": str(args.summary), "html": str(args.html), **summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
