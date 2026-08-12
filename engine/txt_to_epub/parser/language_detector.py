"""
Language detection for text content
"""
import re


def detect_language(content: str) -> str:
    """
    Detect the main language of the text (Korean, Chinese, or English)

    :param content: Text content
    :return: 'korean', 'chinese', or 'english'
    """
    if not content or not content.strip():
        return 'chinese'  # Default to Chinese

    # Count characters from each supported writing system.
    korean_chars = len(re.findall(r'[\uac00-\ud7a3\u1100-\u11ff\u3130-\u318f]', content))
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', content))
    # Count English letters
    english_chars = len(re.findall(r'[a-zA-Z]', content))

    korean_keywords = ['장', '화', '권', '부', '편', '서문', '머리말', '목차', '판권']
    korean_keyword_count = sum(content.count(kw) for kw in korean_keywords)

    # Check common Chinese chapter keywords
    chinese_keywords = ['第', '章', '节', '卷', '部', '篇', '序言', '前言', '目录']
    chinese_keyword_count = sum(content.count(kw) for kw in chinese_keywords)

    # Check common English chapter keywords
    english_keywords = ['Chapter', 'Section', 'Part', 'Book', 'Volume', 'Contents', 'Preface', 'Introduction']
    english_keyword_count = sum(content.lower().count(kw.lower()) for kw in english_keywords)

    # Decision logic
    if korean_chars > max(chinese_chars, english_chars) * 0.5 or korean_keyword_count > max(chinese_keyword_count, english_keyword_count):
        return 'korean'
    if chinese_chars > english_chars * 0.5 or chinese_keyword_count > english_keyword_count:
        return 'chinese'
    else:
        return 'english'
