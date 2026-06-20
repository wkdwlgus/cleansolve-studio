from __future__ import annotations

from tools.style_lab.models import ReferenceSample, StyleLabInputError

CORE_SAMPLE_ROLES: dict[str, str] = {
    "GT_024": "빽빽한 기하 풀이, 도형 위 색상 보조선, 높은 잉크 밀도 기준",
    "GT_036": "여백이 큰 단일 적분 문제, 큰 수식 간격과 줄바꿈 기준",
    "GT_043": "긴 다단계 풀이, 작은 글씨와 색상 강조가 섞인 고밀도 레이아웃",
    "GT_049": "좌표 그래프, 면적 해칭, 파란색 주석 기준",
    "GT_058": "함수 그래프와 구간 표시, 그래프 아래 보조 도형 기준",
    "GT_067": "기하 도형 안 라벨, 보조선, 면적 계산 전개 기준",
    "GT_073": "곡선 그래프, 반복 해칭, 색상 곡선 주석 기준",
    "GT_079": "큰 적분 기호, 루트/분수 수식의 손글씨 질감 기준",
    "GT_082": "큰 좌표축 위 그래프, 도형과 옆 주석이 분리된 구성 기준",
    "GT_086": "한글 설명과 수식 전개가 섞인 문단형 풀이 기준",
    "GT_090": "점근선형 그래프, 그림 아래 compact 수식 전개 기준",
    "GT_099": "붉은 박스 강조, 색상별 수식 계층, 삼각함수 전개 기준",
    "GT_102": "원/삼각형 기하, 높은 파란색 사용량, 라벨 밀도 기준",
    "GT_116": "큰 기하 도형과 sparse 풀이의 균형 기준",
    "GT_132": "가장 높은 잉크 밀도 구간의 기하+수식 혼합 기준",
    "GT_135": "색상 보조선이 많은 기하 풀이, 빨강/파랑 교정 표기 기준",
    "GT_141": "긴 도형 풀이와 색상 수식 블록의 하단 배치 기준",
    "GT_146": "도형 없는 긴 기호 전개, 극한/함수식 줄맞춤 기준",
    "GT_147": "단계형 텍스트+수식 풀이, 색상별 결론 정리 기준",
}

EXTENDED_SAMPLE_IDS: list[str] = [
    "GT_001",
    "GT_003",
    "GT_009",
    "GT_010",
    "GT_019",
    "GT_023",
    "GT_028",
    "GT_037",
    "GT_056",
    "GT_063",
    "GT_075",
    "GT_080",
    "GT_088",
    "GT_091",
    "GT_094",
    "GT_101",
    "GT_104",
    "GT_117",
    "GT_122",
    "GT_129",
    "GT_131",
    "GT_134",
    "GT_137",
    "GT_140",
    "GT_142",
    "GT_145",
]

CORE_SAMPLE_IDS: list[str] = list(CORE_SAMPLE_ROLES)


def validate_reference_contract() -> None:
    if len(CORE_SAMPLE_IDS) != 19:
        raise StyleLabInputError(f"expected 19 core samples, got {len(CORE_SAMPLE_IDS)}")
    if len(EXTENDED_SAMPLE_IDS) != 26:
        raise StyleLabInputError(f"expected 26 extended samples, got {len(EXTENDED_SAMPLE_IDS)}")
    overlap = sorted(set(CORE_SAMPLE_IDS) & set(EXTENDED_SAMPLE_IDS))
    if overlap:
        raise StyleLabInputError(f"core and extended samples overlap: {', '.join(overlap)}")


def build_reference_samples() -> list[ReferenceSample]:
    validate_reference_contract()
    core = [
        ReferenceSample(sample_id=sample_id, tier="core", role=role, filename=f"{sample_id}.png")
        for sample_id, role in CORE_SAMPLE_ROLES.items()
    ]
    extended = [
        ReferenceSample(
            sample_id=sample_id,
            tier="extended",
            role="coverage supplement / regression candidate",
            filename=f"{sample_id}.png",
        )
        for sample_id in EXTENDED_SAMPLE_IDS
    ]
    return core + extended
