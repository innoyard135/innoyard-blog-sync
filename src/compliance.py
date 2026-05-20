"""의료광고·과장 표현 간단 필터 (재작성 후 2차 검사)."""

import re

# 발견 시 경고만 (자동 차단은 하지 않음 — 검수자가 확인)
WARN_PATTERNS: list[tuple[str, str]] = [
    (r"100\s*%|백\s*퍼|완치|반드시|무조건", "과장·단정 표현"),
    (r"지금\s*안\s*하면|방치하면|늦으면\s*큰", "공포 조장"),
    (r"최고의|유일한|1위|압도", "비교·최상급 광고"),
    (r"이노야드|이노밴드|innoband|innoyard", "브랜드명 잔존"),
]


def scan(text: str) -> list[str]:
    warnings: list[str] = []
    for pattern, label in WARN_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            warnings.append(label)
    return warnings
