import sys
import zipfile
import xml.etree.ElementTree as ET
import unicodedata
import html
from pathlib import Path


def extract_paragraphs(xml_data):
    """
    HWPX section XML에서 문단 단위로 텍스트를 추출한다.
    빈 문단도 ""로 보존해서 원본의 줄바꿈 간격을 최대한 유지한다.
    """
    root = ET.fromstring(xml_data)

    paragraphs = []

    for elem in root.iter():
        # HWPX의 문단 태그
        if elem.tag.endswith("}p"):
            parts = []

            # 하나의 문단 안에 여러 run/t 태그가 있을 수 있으므로 모두 합침
            for child in elem.iter():
                if child.tag.endswith("}t"):
                    if child.text is not None:
                        parts.append(child.text)

            paragraph = "".join(parts)

            # 중요:
            # 빈 문단도 삭제하지 않고 그대로 추가
            paragraphs.append(paragraph)

    return paragraphs


def get_section_number(filename):
    """
    Contents/section0.xml
    Contents/section1.xml
    ...
    을 숫자 순서대로 정렬하기 위한 함수
    """
    stem = Path(filename).stem

    try:
        return int(stem.replace("section", ""))
    except ValueError:
        return 999999


def clean_text(text):
    """
    추출된 문자열 후처리
    """

    # &#8212; 같은 HTML/XML entity가 남아 있을 경우 실제 문자로 변환
    text = html.unescape(text)

    # macOS 등에서 발생할 수 있는 한글 자모 분리 문제 교정
    # NFD → NFC
    text = unicodedata.normalize("NFC", text)

    # 줄바꿈 형식 통일
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    return text


def convert_hwpx(filepath):
    """
    HWPX 파일 하나를 TXT로 변환
    """

    path = Path(filepath)

    if not path.exists():
        print(f"[오류] 파일을 찾을 수 없습니다: {path}")
        return

    if path.suffix.lower() != ".hwpx":
        print(f"[오류] HWPX 파일이 아닙니다: {path}")
        return

    paragraphs = []

    try:
        with zipfile.ZipFile(path, "r") as z:

            # HWPX 본문 section 파일 찾기
            section_files = [
                name
                for name in z.namelist()
                if name.startswith("Contents/section")
                and name.endswith(".xml")
            ]

            if not section_files:
                print(f"[오류] 본문 section XML을 찾지 못했습니다: {path.name}")
                return

            # section0 → section1 → section2 순서 보장
            section_files.sort(key=get_section_number)

            for section in section_files:
                try:
                    xml_data = z.read(section)

                    section_paragraphs = extract_paragraphs(xml_data)

                    paragraphs.extend(section_paragraphs)

                except ET.ParseError as e:
                    print(f"[경고] XML 파싱 실패: {section}")
                    print(e)

    except zipfile.BadZipFile:
        print(f"[오류] 정상적인 HWPX/ZIP 파일이 아닙니다: {path}")
        return

    # 각 문단 사이에 줄바꿈 1개 삽입
    #
    # 빈 문단이 "" 형태로 paragraphs 안에 존재하므로
    # 실제 원본의 빈 줄도 자연스럽게 유지됨.
    text = "\n".join(paragraphs)

    text = clean_text(text)

    # 원본 HWPX와 같은 위치에 TXT 생성
    output_path = path.with_suffix(".txt")

    try:
        with open(
            output_path,
            "w",
            encoding="utf-8",
            newline="\n"
        ) as f:
            f.write(text)

    except Exception as e:
        print(f"[오류] TXT 저장 실패: {output_path}")
        print(e)
        return

    print("")
    print("변환 완료!")
    print(f"입력: {path}")
    print(f"출력: {output_path}")
    print("")


def main():

    if len(sys.argv) < 2:
        print("")
        print("사용법:")
        print("")
        print("python3 hwpx_to_txt.py 파일.hwpx")
        print("")
        print("여러 파일도 동시에 가능합니다:")
        print("")
        print("python3 hwpx_to_txt.py 1.hwpx 2.hwpx 3.hwpx")
        print("")
        return

    # 여러 HWPX 파일 일괄 변환
    for filepath in sys.argv[1:]:

        try:
            convert_hwpx(filepath)

        except Exception as e:
            print("")
            print(f"[오류] 변환 중 예상하지 못한 문제가 발생했습니다.")
            print(f"파일: {filepath}")
            print(e)
            print("")


if __name__ == "__main__":
    main()