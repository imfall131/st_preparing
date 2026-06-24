"""
preprocessing.py
딸기 스마트팜 환경 데이터 전처리 모듈

- JSON 레코드 리스트 로드
- 필수 필드 검증 및 타입 캐스팅
- 결측치(None) 제거
- IQR 기반 이상치 제거 (생장단계별 그룹 내에서 수행)
"""

import json
from typing import List, Dict, Any

# 필수 필드 정의
ENV_FIELDS = ["temperature", "humidity", "co2"]
GROWTH_FIELDS = ["flower_count", "leaf_area", "stem_area"]
TARGET_FIELD = "yield_amount"
REQUIRED_FIELDS = ["farm_id", "growth_stage"] + ENV_FIELDS + GROWTH_FIELDS + [TARGET_FIELD]


def load_records(json_path: str) -> List[Dict[str, Any]]:
    """JSON 파일에서 레코드 리스트를 로드한다."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("JSON 데이터는 레코드(dict)의 리스트 형태여야 합니다.")
    return data


def validate_and_clean(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    필수 필드 누락/None 값이 있는 레코드를 제거하고,
    숫자 필드를 float으로 캐스팅한다.
    """
    cleaned = []
    dropped_missing = 0

    for rec in records:
        # 필수 필드 존재 여부 확인
        if any(field not in rec or rec[field] is None for field in REQUIRED_FIELDS):
            dropped_missing += 1
            continue

        try:
            new_rec = dict(rec)
            new_rec["growth_stage"] = int(rec["growth_stage"])
            for field in ENV_FIELDS + GROWTH_FIELDS + [TARGET_FIELD]:
                new_rec[field] = float(rec[field])
            cleaned.append(new_rec)
        except (ValueError, TypeError):
            dropped_missing += 1
            continue

    print(f"[전처리] 결측치/형식 오류로 제거된 레코드: {dropped_missing}개")
    return cleaned


def remove_outliers_by_stage(
    records: List[Dict[str, Any]],
    fields: List[str],
    k: float = 1.5,
) -> List[Dict[str, Any]]:
    """
    생장단계(growth_stage)별로 그룹을 나누어 IQR 기반 이상치를 제거한다.
    fields에 포함된 모든 필드가 정상 범위 안에 있어야 레코드가 유지된다.
    """
    by_stage: Dict[int, List[Dict[str, Any]]] = {}
    for rec in records:
        by_stage.setdefault(rec["growth_stage"], []).append(rec)

    result = []
    dropped_outliers = 0

    for stage, group in by_stage.items():
        bounds = {}
        for field in fields:
            values = sorted(r[field] for r in group)
            n = len(values)
            if n < 4:
                bounds[field] = (float("-inf"), float("inf"))
                continue
            q1 = values[n // 4]
            q3 = values[(3 * n) // 4]
            iqr = q3 - q1
            lower = q1 - k * iqr
            upper = q3 + k * iqr
            bounds[field] = (lower, upper)

        for rec in group:
            is_outlier = any(
                not (bounds[field][0] <= rec[field] <= bounds[field][1])
                for field in fields
            )
            if is_outlier:
                dropped_outliers += 1
            else:
                result.append(rec)

    print(f"[전처리] 이상치로 제거된 레코드: {dropped_outliers}개")
    return result


def preprocess_pipeline(json_path: str) -> List[Dict[str, Any]]:
    """전처리 전체 파이프라인 실행"""
    raw = load_records(json_path)
    print(f"[전처리] 원본 레코드 수: {len(raw)}개")

    cleaned = validate_and_clean(raw)

    # 수확량(yield_amount)은 1~4단계에서는 의미가 없는 값(0)이므로
    # 이상치 검사는 환경값 + 생장지표 기준으로만 수행한다.
    outlier_check_fields = ENV_FIELDS + GROWTH_FIELDS
    final = remove_outliers_by_stage(cleaned, outlier_check_fields)

    print(f"[전처리] 최종 레코드 수: {len(final)}개")
    return final


if __name__ == "__main__":
    data = preprocess_pipeline("/home/claude/strawberry_smartfarm/sample_farm_data.json")
    print(data[:2])
