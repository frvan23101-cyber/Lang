spaCy NLP 분석 전용 재현 묶음

포함 자료: 최종 선정 기사 130개의 추출된 지시문 1,534개, 기사 선정표, spaCy 절단/가열 분석 코드, 집계 코드

Python 3.10 이상에서:
python -m pip install "spacy==3.8.18"
python -m spacy download en_core_web_sm
python -m spacy download fr_core_news_sm
python -m spacy download de_core_news_sm
python run_complete.py

**코드 정리 및 일부 작성 과정에서 LLM을 사용했음을 밝힙니다**
