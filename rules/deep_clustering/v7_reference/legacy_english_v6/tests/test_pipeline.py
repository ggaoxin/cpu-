from topicfusion_v6.pipeline import extract_views
def test_views():
 t,a=extract_views('A randomized trial','We conducted a randomized controlled trial in patients.',['trial'])
 assert '[TITLE]' in t and '[OBJECTIVE_CONTEXT]' in a
