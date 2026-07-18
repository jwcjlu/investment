from __future__ import annotations

import json
import os
from typing import Any, Optional

from engine.curriculum.models import Module
from engine.llm import create_structured, make_client

QUIZ_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "minItems": 2,
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "stem": {"type": "string"},
                    "options": {
                        "type": "array",
                        "minItems": 4,
                        "maxItems": 4,
                        "items": {"type": "string"},
                    },
                    "answer_index": {"type": "integer", "minimum": 0, "maximum": 3},
                    "explanation": {"type": "string"},
                },
                "required": ["id", "stem", "options", "answer_index", "explanation"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["questions"],
    "additionalProperties": False,
}

MAX_TOKENS = 2000


def _safe_tag(tag: str) -> str:
    return tag.replace("/", "_")


def _quiz_path(quizzes_dir: str, tag: str) -> str:
    return os.path.join(quizzes_dir, f"{_safe_tag(tag)}.json")


def _placeholder_question(
    module: Module,
    lesson,
    q_num: int,
    *,
    stem: str,
    wrong: str,
) -> dict[str, Any]:
    return {
        "id": f"q{q_num}",
        "stem": stem,
        "options": [
            f"《{lesson.book_title}》：{lesson.opinion}",
            wrong,
            "以上都不对",
            "无法判断",
        ],
        "answer_index": 0,
        "explanation": f"该观点来自《{lesson.book_title}》，属于「{module.tag}」主题。",
    }


def placeholder_quiz(module: Module) -> dict[str, Any]:
    if not module.lessons:
        questions = [
            {
                "id": "q1",
                "stem": f"「{module.tag}」模块目前暂无观点，以下说法正确的是？",
                "options": [
                    "需要先补充该模块的学习材料",
                    "可以直接跳过所有练习",
                    "模块内容已完整覆盖",
                    "无需任何学习即可掌握",
                ],
                "answer_index": 0,
                "explanation": "模块暂无观点时，应先补充学习材料再继续。",
            },
            {
                "id": "q2",
                "stem": f"关于「{module.tag}」模块，以下哪项最合理？",
                "options": [
                    "完成观点录入后再进行测验",
                    "测验与模块内容无关",
                    "空模块也能自动满分",
                    "可随意填写任意答案",
                ],
                "answer_index": 0,
                "explanation": "有内容支撑时，测验才更有意义。",
            },
        ]
    elif len(module.lessons) == 1:
        lesson = module.lessons[0]
        questions = [
            _placeholder_question(
                module,
                lesson,
                1,
                stem=f"以下哪一项属于「{module.tag}」模块的核心观点？",
                wrong="与本模块主题无关的表述",
            ),
            _placeholder_question(
                module,
                lesson,
                2,
                stem=f"《{lesson.book_title}》中，哪一项最能代表「{module.tag}」主题？",
                wrong=f"与本主题无关的其他投资技巧",
            ),
        ]
    else:
        questions = []
        for i, lesson in enumerate(module.lessons[:2], 1):
            other = module.lessons[i % len(module.lessons)]
            wrong = f"《{other.book_title}》中的观点：{other.opinion[:30]}"
            questions.append(
                _placeholder_question(
                    module,
                    lesson,
                    i,
                    stem=f"以下哪一项属于「{module.tag}」模块的核心观点？",
                    wrong=wrong,
                )
            )

    return {
        "tag": module.tag,
        "source": "placeholder",
        "questions": questions,
    }


def save_quiz(quiz: dict[str, Any], quizzes_dir: str) -> None:
    os.makedirs(quizzes_dir, exist_ok=True)
    path = _quiz_path(quizzes_dir, quiz["tag"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(quiz, f, ensure_ascii=False, indent=2)


def load_quiz(tag: str, quizzes_dir: str) -> Optional[dict[str, Any]]:
    path = _quiz_path(quizzes_dir, tag)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _build_prompt(module: Module) -> str:
    lines = [
        f"请为投资学习路径中的「{module.tag}」主题模块出 2-3 道单选题。",
        "每题 4 个选项，给出正确答案索引（0-3）和简短解析。",
        "题干应基于以下观点摘要，不得照抄金句作为唯一线索，但须忠于笔记内容。",
        "",
    ]
    for i, lesson in enumerate(module.lessons, 1):
        lines.append(
            f"{i}. 《{lesson.book_title}》{lesson.chapter} — {lesson.opinion}"
            f"（论据：{lesson.argument_summary}；可执行度：{lesson.actionability}）"
        )
    lines.extend([
        "",
        "请输出 JSON，包含 questions 数组，每题字段：",
        "id, stem, options（4 个字符串）, answer_index, explanation",
    ])
    return "\n".join(lines)


def generate_ai_quiz(module: Module) -> dict[str, Any]:
    client = make_client()
    data = create_structured(
        client,
        prompt=_build_prompt(module),
        schema=QUIZ_SCHEMA,
        max_tokens=MAX_TOKENS,
    )
    questions = data["questions"]
    if not (2 <= len(questions) <= 3):
        raise RuntimeError(f"期望 2-3 道题，实际 {len(questions)} 道")
    return {
        "tag": module.tag,
        "source": "ai",
        "questions": questions,
    }


def get_or_create_quiz(
    module: Module,
    quizzes_dir: str,
    use_ai: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    if not force:
        cached = load_quiz(module.tag, quizzes_dir)
        if cached is not None:
            return cached

    if use_ai:
        try:
            quiz = generate_ai_quiz(module)
            save_quiz(quiz, quizzes_dir)
            return quiz
        except Exception as e:
            print(f"      警告：AI 出题失败，回退占位题：{e}")

    quiz = placeholder_quiz(module)
    save_quiz(quiz, quizzes_dir)
    return quiz


def grade(quiz: dict[str, Any], answers: dict[str, int]) -> dict[str, Any]:
    details = []
    score = 0
    for q in quiz.get("questions") or []:
        qid = q["id"]
        chosen = answers.get(qid)
        correct = chosen == q["answer_index"]
        if correct:
            score += 1
        details.append({
            "id": qid,
            "correct": correct,
            "explanation": q.get("explanation", ""),
        })
    return {"score": score, "details": details}
