"""Isolated UI fixture. Synthetic descriptions, never a paid service call."""
import json
from imprint_review_server import app


class Model:
    def observe_pet_memory(self, image, prompt):
        if '"events"' in prompt:
            return json.dumps(dict(subject='single',events=[dict(first=1,last=1,action='sit',observation='测试事件：坐在地面上')]),ensure_ascii=False)
        return '{"observations":[{"quote":"测试用姿态观察。","frame":1}]}'


app.extensions['llm']=Model()
if __name__=='__main__':
    app.run(host='127.0.0.1',port=5058,debug=False,use_reloader=False)
