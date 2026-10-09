from contextlib import asynccontextmanager
import random
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
import regex

class Score(BaseModel):
    author: str = Field(..., examples=["tolkien"], description="Имя автора")
    score: float = Field(..., ge=0, le=1, description="Вероятность принадлежности текста автору")

class AnalyzeResponse(BaseModel):
    suspected_author: str = Field(..., examples=["rowling"], description="Наиболее вероятный автор")
    score: float = Field(..., ge=0, le=1, description="Уверенность модели")
    # TODO: исправить на настоящий тип
    style_features: str = Field(..., description="Стилистические характеристики автора")
    top_scores: list[Score] = Field(..., description="Остальные кандидаты по убыванию")

def load_model() -> bool:
    return True

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.is_model_loaded = load_model()
    yield
    
app = FastAPI(lifespan=lifespan, title="Stylometry API", description="""API для стилометрического анализа: определение автора 
фрагмента текста среди фэнтези-писателей.""")

@app.get('/api/health', tags=["service"], summary="Проверка доступности сервиса")
def health():
    if app.state.is_model_loaded:
        return 'ok'
    return 'model_unavailable'

def is_latin(text: str) -> bool:
    if len(regex.findall(r'(?![a-zA-Z])\p{L}', text)) > 0:
        return False
    else:
        return True

@app.get('/api/analyze', response_model=AnalyzeResponse, tags=["analysis"], summary="Определение автора фрагмента")
def define_author(text: str = Query(...,
                                    description='Текст для анализа на английском языке',
                                    json_schema_extra={
                                        "minLength": 1,
                                        "maxLength": 2500
                                    }
                                    )) -> AnalyzeResponse: #= Query(..., min_length=1, max_length=2500)) 
    '''функция-заглушка для определения автора фрагмента'''
    if len(text) == 0: 
        raise HTTPException(status_code=400, detail= {'error': 'empty_text', 
                                                      'message': 'Текст не должен быть пустым'})                                            
    if len(text) > 2500:
        raise HTTPException(status_code=400, detail= {'error': 'text_too_long',
                                                      'message': 'Текст длиннее 2500 символов',
                                                      'limit': 2500})
    if not is_latin(text):
        raise HTTPException(status_code=400, detail= {'error': 'unsupported_language',
                                                      'message': 'Поддерживается только латиница'})
    if not app.state.is_model_loaded:
        raise HTTPException(status_code=503, detail= {'error': 'model_unavailable',
                                                      'message': 'Модель не загружена'})
    authors = ["lewis", "martin", "pratchett", "rowling", "tolkien"]
    all_scores = sorted(
        [{'author': random.choice(authors), 'score': round(random.random(), 2)} for a in range(4)],
        key=lambda x: x.get('score'),
        reverse=True
    )
    style_features = 'стилистические характеристики автора'
    return {
        'suspected_author': all_scores[0]['author'],
        'score': all_scores[0]['score'],
        'style_features': style_features ,
        'top_scores': all_scores[1:]
    }
