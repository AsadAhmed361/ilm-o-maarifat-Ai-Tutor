"""
services/grader.py

Pure deterministic MCQ grading -- no AI dependency.
"""


class Grader:
    def grade(self, results: list[dict]) -> dict:
        graded = []
        topic_stats = {}

        for q in results:
            is_correct = q["student_answer"] == q["correct_option"]

            graded.append({
                "question": q["question"],
                "topic": q["topic"],
                "correct_option": q["correct_option"],
                "student_answer": q["student_answer"],
                "is_correct": is_correct,
            })

            topic = q["topic"]
            if topic not in topic_stats:
                topic_stats[topic] = {"correct": 0, "total": 0}
            topic_stats[topic]["total"] += 1
            if is_correct:
                topic_stats[topic]["correct"] += 1

        total_correct = sum(1 for g in graded if g["is_correct"])
        total_questions = len(graded)

        return {
            "total_score": total_correct,
            "total_questions": total_questions,
            "percentage": round((total_correct / total_questions) * 100, 2) if total_questions else 0,
            "topic_breakdown": topic_stats,
            "graded_questions": graded,
        }
