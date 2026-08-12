import sys
sys.path.insert(0, './src')

from txt_to_epub.core import txt_to_epub
from txt_to_epub.parser_config import ParserConfig

# 1. 원고의 '1장', '2장', '004화' 등을 정밀하게 감지하는 정규식 패턴 설정
config = ParserConfig(
    custom_chapter_patterns=[
        # '1장 제목', '2장 제목' 패턴 감지 (줄 전체가 아닌 1장/2장 패턴만 타겟팅)
        r"^\d+\s*장\s+[^\r\n]+",
        
        # 맨 마지막 '판권' 섹션 독립 분리
        r"^판권$"
    ],
    
    # 문단 구분선인 '* * *'이나 기타 특수문자 라인은 챕터로 감지되지 않도록 예외 처리
    ignore_patterns=[
        r"^\s*\*\s*\*\s*\*\s*$",  # '* * *' 문단 구분선 보호
        r"^\s*목차\s*$"           # 본문 상단의 단순 '목차' 글자 무시
    ],
    
    min_chapter_length=0,
    enable_chapter_validation=False,
    
    # 중국어/개발사 워터마크 비활성화
    enable_watermark=False,
    watermark_text=""
)

try:
    # 2. EPUB 변환 및 메타데이터 설정
    result = txt_to_epub(
        txt_file="바람난1권.txt",          # 원고 텍스트 파일명
        epub_file="final_test.epub",      # 생성될 EPUB 파일명
        title="바람난 아내를 버리고 시골로 갔더니 수백억이 들어왔다 1권",
        author="육쾌남",
        cover_image="cover.png",          # 표지 이미지 파일명 (같은 폴더에 위치 필수)
        config=config,
        metadata_overrides={
            "language": "ko"
        }
    )
    print("🎉 변환 성공! '1장', '2장' 챕터 분할 및 '* * *' 문단 구분이 모두 적용되었습니다.")
except Exception as e:
    print(f"❌ 에러 발생: {e}")
