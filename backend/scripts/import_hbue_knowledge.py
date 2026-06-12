import asyncio
import json
import os
import sys
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from core.database import async_engine
from models.knowledge_base import Document, FAQ


def _json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False)


HBUE_DOCS = [
    {
        "title": "湖北经济学院学校简介（摘录）",
        "category": "general",
        "subcategory": "school_profile",
        "source": "http://www.hbue.edu.cn/432/list.htm",
        "file_type": "html",
        "language": "zh-CN",
        "tags": ["湖北经济学院", "学校简介", "地址", "邮编"],
        "content": """湖北经济学院是湖北省人民政府举办的全日制普通本科院校，国务院学位委员会批准的硕士学位授予单位，国家“十四五”教育强国推进工程支持高校。
学校办学历史最早可追溯到1907年张之洞创办的“湖北商业中学堂”，于2002年3月经教育部批准，由原湖北商业高等专科学校、武汉金融高等专科学校、湖北省计划管理干部学院合并组建。
学校现设本科专业56个，全日制普通本科在校生19057人；2012年起开办硕士研究生教育，2021年获批硕士学位授予单位，现开办应用经济学1个一级学科硕士学位授权点，会计、金融、法律、应用统计、税务、保险、数字经济、公共管理、旅游管理和审计10个专业硕士学位授权点。
学校位于武汉市光谷科创大走廊腹地，坐落在风景秀丽的汤逊湖畔。

地址：武汉市江夏区藏龙岛开发区杨桥湖大道8号
邮编：430205
（数据更新时间：2025年11月）""",
    },
    {
        "title": "湖北经济学院信息公开受理机构与监督机构",
        "category": "administrative",
        "subcategory": "information_disclosure",
        "source": "https://xxgk.hbue.edu.cn/",
        "file_type": "html",
        "language": "zh-CN",
        "tags": ["信息公开", "学校办公室", "纪委", "电话", "邮箱", "办公地点"],
        "content": """信息公开受理机构：学校办公室
办公时间：校历规定工作日 8:00-12:00，14:00-17:00
联系电话：027-81978119
传真号码：027-81973710
接访电话：027-81978119
电子邮箱：xxgk@hbue.edu.cn
办公地点：湖北省武汉市江夏区藏龙岛开发区杨桥湖大道8号（行政楼A416）

信息公开监督机构：纪委（监专办）综合室
办公时间：校历规定工作日 8:00-12:00，14:00-17:00
投诉电话：027-81973936
办公地点：湖北省武汉市江夏区藏龙岛开发区杨桥湖大道8号（行政四楼406）

学校地址：武汉市江夏区藏龙岛开发区杨桥湖大道8号
邮政编码：430205""",
    },
    {
        "title": "湖北经济学院财务处（办事指南/收费管理入口）",
        "category": "finance",
        "subcategory": "finance_office",
        "source": "http://cwc.hbue.edu.cn/",
        "file_type": "html",
        "language": "zh-CN",
        "tags": ["财务处", "缴费", "报销", "电子票据", "收费目录"],
        "content": """财务处网站栏目（部分）：
- 办事指南：https://cwc.hbue.edu.cn/856/list.htm
- 收费管理：https://cwc.hbue.edu.cn/857/list.htm

办事指南（示例条目，具体以网页为准）：
- 【报销】票据粘贴规范说明
- 【综合】单位公务卡用卡十二问

收费管理（示例条目，具体以网页为准）：
- 学生网上缴费及电子票据下载指南
- 新生入学缴费常见问题解答
- 普通本科学分制收费相关说明

提示：如需办理缴费/票据下载/报销等事项，建议优先访问财务处官网对应栏目查看最新通知与指南。""",
    },
    {
        "title": "选课流程与注意事项",
        "category": "academic",
        "subcategory": "course_selection",
        "source": "教务处",
        "file_type": "text",
        "language": "zh-CN",
        "tags": ["选课", "教务系统", "学分", "选课流程"],
        "content": """选课流程：
1. 登录教务系统（http://jwc.hbue.edu.cn）
2. 点击"网上选课"菜单
3. 仔细阅读选课通知，注意选课时间段（通常分为初选、正选、退补选三个阶段）
4. 在对应选课阶段内，根据培养方案选择专业课、公选课等
5. 确认选课结果无误后保存并退出。

注意事项：
- 避免在临近结束时选课以免网络拥堵。
- 注意课程容量，公选课实行先到先得或抽签制。
- 选课结束后务必在“我的课表”中确认是否选上。""",
    },
    {
        "title": "学生成绩查询指南",
        "category": "academic",
        "subcategory": "grade_query",
        "source": "教务处",
        "file_type": "text",
        "language": "zh-CN",
        "tags": ["成绩查询", "教务处", "绩点", "补考"],
        "content": """成绩查询途径：
1. 电脑端：登录教务管理系统 -> 信息查询 -> 学生成绩查询。可以查看本学期成绩、历年成绩以及绩点情况。
2. 移动端：通过“微校园”APP或微信企业号，在“教务服务”模块点击“成绩查询”。

说明：
- 期末考试成绩通常在考试结束后1-2周内由任课老师录入系统。
- 如对成绩有异议，需在下学期开学前两周内向开课学院提交成绩复核申请。
- 补考和重修成绩会在相应考试后单独发布。""",
    },
    {
        "title": "图书馆开放时间及借阅规则",
        "category": "library",
        "subcategory": "rules",
        "source": "图书馆",
        "file_type": "text",
        "language": "zh-CN",
        "tags": ["图书馆", "开放时间", "借书", "自习室"],
        "content": """图书馆开放时间：
- 自习区：周一至周日 7:00 - 22:30
- 借阅室（各楼层）：周一至周日 8:00 - 22:00
- 国家法定节假日及寒暑假开放时间另行通知。

借阅规则：
1. 凭本人校园卡借阅。
2. 本科生借书数量上限：15册，借期：30天。
3. 可在到期前续借1次，续期15天。
4. 逾期未还将产生逾期使用费，每天0.1元/册。""",
    }
]


HBUE_FAQS = [
    {
        "question": "湖北经济学院地址和邮编是什么？",
        "answer": "湖北经济学院地址：武汉市江夏区藏龙岛开发区杨桥湖大道8号；邮编：430205。",
        "category": "general",
        "subcategory": "contact",
        "keywords": ["地址", "邮编", "杨桥湖大道8号", "430205"],
        "priority": 5,
    },
    {
        "question": "湖北经济学院信息公开受理机构联系方式是什么？",
        "answer": "信息公开受理机构：学校办公室。办公时间：工作日8:00-12:00，14:00-17:00；电话：027-81978119；传真：027-81973710；邮箱：xxgk@hbue.edu.cn；地点：行政楼A416（武汉市江夏区藏龙岛开发区杨桥湖大道8号）。",
        "category": "administrative",
        "subcategory": "information_disclosure",
        "keywords": ["信息公开", "学校办公室", "电话", "邮箱"],
        "priority": 5,
    },
    {
        "question": "湖北经济学院信息公开监督机构（投诉）电话是多少？",
        "answer": "信息公开监督机构：纪委（监专办）综合室；投诉电话：027-81973936；地点：行政四楼406。",
        "category": "administrative",
        "subcategory": "information_disclosure",
        "keywords": ["信息公开", "监督", "投诉", "纪委"],
        "priority": 4,
    },
    {
        "question": "如何查询本学期的期末成绩？",
        "answer": "你可以登录学校教务系统，在“信息查询”栏目下点击“学生成绩查询”。也可以通过手机端“微校园”的教务服务模块进行快速查询。如果成绩还没有出，可能是老师还没有录入系统，请耐心等待。",
        "category": "academic",
        "subcategory": "grade",
        "keywords": ["成绩查询", "期末成绩", "教务系统"],
        "priority": 5,
    },
    {
        "question": "图书馆几点开门？",
        "answer": "图书馆自习区每天早上7:00开放，晚上22:30关闭。各楼层的借阅室开放时间为早上8:00到晚上22:00。寒暑假和法定节假日的开放时间请关注图书馆官网通知。",
        "category": "library",
        "subcategory": "hours",
        "keywords": ["图书馆", "开放时间", "开门", "关门"],
        "priority": 4,
    }
]


async def import_hbue() -> None:
    async with AsyncSession(async_engine) as session:
        for doc in HBUE_DOCS:
            existing = await session.execute(select(Document).where(Document.title == doc["title"]))
            if existing.scalar_one_or_none():
                continue

            record = Document(
                title=doc["title"],
                content=doc["content"],
                category=doc["category"],
                subcategory=doc.get("subcategory"),
                source=doc.get("source"),
                file_type=doc.get("file_type", "text"),
                language=doc.get("language", "zh-CN"),
                tags=_json_text(doc.get("tags", [])),
                meta_data={
                    "imported_from": doc.get("source"),
                    "imported_at": datetime.utcnow().isoformat() + "Z",
                },
                is_active=True,
                is_public=True,
            )
            session.add(record)

        for faq in HBUE_FAQS:
            existing = await session.execute(select(FAQ).where(FAQ.question == faq["question"]))
            if existing.scalar_one_or_none():
                continue

            record = FAQ(
                question=faq["question"],
                answer=faq["answer"],
                category=faq["category"],
                subcategory=faq.get("subcategory"),
                keywords=_json_text(faq.get("keywords", [])),
                priority=faq.get("priority", 1),
                is_active=True,
                created_by="system:hbue_import",
            )
            session.add(record)

        await session.commit()


if __name__ == "__main__":
    asyncio.run(import_hbue())
