spaCy NLP 분석 전용 재현 묶음

포함 자료: 최종 선정 기사 130개의 추출된 지시문 1,534개, 기사 선정표, spaCy 절단/가열 분석 코드, 집계 코드. 원문에서 지시문을 다시 추출하는 전처리 코드나 이전 휴리스틱 분석 코드는 포함하지 않습니다.

Python 3.10 이상에서:
python -m pip install "spacy==3.8.18"
python -m spacy download en_core_web_sm
python -m spacy download fr_core_news_sm
python -m spacy download de_core_news_sm
python run_complete.py

포스터 결과: poster_fr_de_summary.csv, poster_fr_de_articles.csv.
전체 결과: all_domain_country_summary.csv, all_domain_article_scores.csv.
동사/단서 감사: nlp_cutting_audit.csv, other_actions_audit.csv.
프랑스/독일 절단/가열 결과에 한해 E>0 기사만 집계하며 기사별 지수는 (E+1)/(A+2)입니다. 모델 버전은 실행 후 nlp_reproduction_manifest.json에 저장됩니다.
