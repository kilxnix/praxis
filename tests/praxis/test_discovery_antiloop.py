from praxis.discovery import question_too_similar

def test_question_too_similar_catches_rephrase():
    recent = [
        "When you\'re chatting to figure out their vibe, is that mostly smooth creative talk, "
        "or do you find yourself constantly re-typing the same details they tell you just so "
        "we can get them into your contract?"
    ]
    again = (
        "When you\'re chatting to figure out their \"vibe,\" is that mostly smooth creative talk, "
        "or do you find yourself constantly re-typing the same details they tell you just so we "
        "can get them into your contract?"
    )
    assert question_too_similar(again, recent) is True
    assert question_too_similar(
        "Once you finish filming, what is the very next thing you do with the footage?",
        recent,
    ) is False
