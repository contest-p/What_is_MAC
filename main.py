"""
Mini NPU Simulator
- MAC(Multiply-Accumulate) 연산으로 패턴(Cross / X)을 판별하는 콘솔 프로그램
- 외부 라이브러리 없이 표준 라이브러리만 사용
"""
import json
import os
import re
import time

# ==================================================
# 상수
# ==================================================
EPSILON = 1e-9  # 두 점수 차이가 이보다 작으면 "동점"으로 본다 (부동소수점 오차 대비)
REPEAT = 10      # 성능 측정 반복 횟수
UNDECIDED = "UNDECIDED"          # 동점일 때의 판정값
PERF_SIZES = [3, 5, 13, 25]      # 성능 분석에 사용할 크기 목록
DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")

# 라벨 정규화 표: 데이터마다 제각각인 표기를 프로그램 내부 "표준 라벨" 2개로 통일
LABEL_MAP = {
    "+": "Cross", "cross": "Cross",   # expected의 '+', 필터 키의 'cross'
    "x": "X",                          # expected/필터 키의 'x'
}


# ==================================================
# [1단계] 데이터 구조 + MAC 연산 + 판정
# ==================================================
def create_matrix(n, fill=0.0):
    """n×n 2차원 배열(리스트의 리스트)을 만든다. matrix[i][j]로 값을 읽고/쓴다."""
    return [[fill for _ in range(n)] for _ in range(n)]


def mac(pattern, filt):
    """
    MAC 연산: 같은 위치의 값끼리 곱하고(Multiply) 전부 더한다(Accumulate).
    점수가 클수록 패턴과 필터가 닮았다는 뜻.
    """
    n = len(pattern)
    total = 0.0
    for i in range(n):          # 행
        for j in range(n):      # 열
            total += pattern[i][j] * filt[i][j]
    return total


def judge(score_a, score_b, label_a="A", label_b="B"):
    """
    두 점수를 비교해 판정한다.
    - 차이가 EPSILON보다 작으면 동점 → "UNDECIDED"
    - 아니면 점수가 큰 쪽의 라벨을 반환
    """
    if abs(score_a - score_b) < EPSILON:
        return UNDECIDED
    return label_a if score_a > score_b else label_b


# ==================================================
# [2단계 · 보너스] 패턴 생성기
# ==================================================
def make_cross(n):
    """N×N 십자가 패턴: 가운데 행 + 가운데 열을 1로 채운다. (홀수 N 권장)"""
    m = create_matrix(n)
    mid = n // 2
    for i in range(n):
        m[mid][i] = 1.0   # 가운데 가로줄
        m[i][mid] = 1.0   # 가운데 세로줄
    return m


def make_x(n):
    """N×N X 패턴: 두 대각선(↘, ↙)을 1로 채운다."""
    m = create_matrix(n)
    for i in range(n):
        m[i][i] = 1.0           # ↘ 대각선 (행 == 열)
        m[i][n - 1 - i] = 1.0   # ↙ 대각선 (행 + 열 == n-1)
    return m


# ==================================================
# [보너스] 1차원 배열 최적화
# ==================================================
def flatten(m):
    """N×N 2차원 배열을 길이 N²의 1차원 배열로 편다. (i행 j열 → 인덱스 i*N + j)"""
    return [v for row in m for v in row]


def mac_flat(a, b):
    """1차원 배열용 MAC: 행/열 이중 반복 대신 반복문 하나로 N²번 곱하고 더한다."""
    total = 0.0
    for k in range(len(a)):
        total += a[k] * b[k]
    return total


# ==================================================
# 공통 출력 / 성능 측정 도구
# ==================================================
def print_section(title):
    print()
    print("#" + "-" * 40)
    print(f"# {title}")
    print("#" + "-" * 40)


def print_matrix(m):
    for row in m:
        print("  " + " ".join(f"{v:g}" for v in row))


def measure_ms(func, a, b, repeat=REPEAT):
    """
    연산 함수 func(a, b)만 repeat번 반복 실행해 평균 시간(ms)을 잰다.
    입력/출력/파일 읽기 시간은 빼고 '연산 함수 호출 구간'만 측정한다.
    """
    start = time.perf_counter()
    for _ in range(repeat):
        func(a, b)
    end = time.perf_counter()
    return (end - start) / repeat * 1000   # 초 → ms


def print_perf_table(sizes):
    """크기 목록을 받아 '크기 / 평균 시간(ms) / 연산 횟수(N²)' 표를 출력한다."""
    print(f"{'크기':<10}{'평균 시간(ms)':>16}{'연산 횟수(N²)':>16}{'1회당(μs)':>14}")
    print("-" * 58)
    for n in sizes:
        pattern, filt = make_cross(n), make_x(n)   # 생성기로 동일 조건 입력 생성
        avg = measure_ms(mac, pattern, filt)
        per_op_us = avg * 1000 / (n * n)           # 곱셈 1번당 시간 → 거의 일정하면 O(N²)
        print(f"{f'{n}×{n}':<10}{avg:>16.4f}{n * n:>16}{per_op_us:>14.4f}")


def print_optimization_table(sizes):
    """[보너스] 같은 입력·같은 반복 횟수로 2차원(mac) vs 1차원(mac_flat) 속도를 비교한다."""
    print(f"{'크기':<10}{'2차원(ms)':>14}{'1차원(ms)':>14}{'속도 향상':>12}")
    print("-" * 50)
    for n in sizes:
        pattern, filt = make_cross(n), make_x(n)
        flat_p, flat_f = flatten(pattern), flatten(filt)   # 변환은 측정 구간 밖에서 1번만
        t2d = measure_ms(mac, pattern, filt)
        t1d = measure_ms(mac_flat, flat_p, flat_f)
        ratio = t2d / t1d if t1d > 0 else float("inf")
        print(f"{f'{n}×{n}':<10}{t2d:>14.4f}{t1d:>14.4f}{ratio:>11.2f}배")


def ask_choice(prompt):
    """'1' 또는 '2'를 입력할 때까지 다시 묻는다."""
    while True:
        choice = input(f"{prompt}: ").strip()
        if choice in ("1", "2"):
            return choice
        print("1 또는 2를 입력하세요.")


# ==================================================
# [3단계] 모드 1 - 사용자 입력 (3×3)
# ==================================================
def read_matrix(name, n=3):
    """
    n×n 행렬을 한 줄씩(공백 구분) 입력받는다.
    - 숫자 개수가 n개가 아니거나, 숫자로 바꿀 수 없으면 안내 후 그 줄을 다시 입력받는다.
    """
    print(f"{name} ({n}줄 입력, 공백 구분)")
    matrix = []
    while len(matrix) < n:
        line = input(f"  {len(matrix) + 1}행> ")
        parts = line.split()
        if len(parts) != n:
            print(f"  입력 형식 오류: 각 줄에 {n}개의 숫자를 공백으로 구분해 입력하세요. "
                  f"(입력된 개수: {len(parts)})")
            continue
        try:
            row = [float(x) for x in parts]
        except ValueError:
            print("  입력 형식 오류: 숫자만 입력하세요. (예: 0 1 0)")
            continue
        matrix.append(row)
    return matrix


def run_user_mode():
    n = 3

    print_section("[1] 필터 입력")
    if ask_choice("필터 입력 방식 (1: 직접 입력, 2: 패턴 생성기로 자동 생성)") == "1":
        filter_a = read_matrix("필터 A", n)
        print()
        filter_b = read_matrix("필터 B", n)
    else:
        filter_a, filter_b = make_cross(n), make_x(n)   # 보너스: A=Cross, B=X 자동 생성
    print("\n✓ 필터 저장 완료")
    print(" 필터 A:"); print_matrix(filter_a)
    print(" 필터 B:"); print_matrix(filter_b)

    print_section("[2] 패턴 입력")
    pattern = read_matrix("패턴", n)

    print_section("[3] MAC 결과")
    score_a = mac(pattern, filter_a)
    score_b = mac(pattern, filter_b)
    avg_ms = measure_ms(mac, pattern, filter_a)
    print(f"A 점수: {score_a}")
    print(f"B 점수: {score_b}")
    print(f"연산 시간(평균/{REPEAT}회): {avg_ms:.4f} ms")
    result = judge(score_a, score_b, "A", "B")
    if result == UNDECIDED:
        print(f"판정: 판정 불가 (|A-B| < {EPSILON})")
    else:
        print(f"판정: {result}")

    print_section(f"[4] 성능 분석 (평균/{REPEAT}회)")
    print_perf_table([3])


# ==================================================
# [4단계] 모드 2 - data.json 분석
# ==================================================
def normalize_label(raw):
    """'+', 'cross', 'x', ' X ' 등 → 'Cross' 또는 'X'. 모르는 값이면 None."""
    if not isinstance(raw, str):
        return None
    return LABEL_MAP.get(raw.strip().lower())


def check_square(m, n):
    """m이 n×n 숫자 배열인지 검사. 문제가 있으면 사유(문자열), 정상이면 None."""
    if not isinstance(m, list) or len(m) != n:
        rows = len(m) if isinstance(m, list) else "?"
        return f"행 수 불일치 (기대 {n}, 실제 {rows})"
    for i, row in enumerate(m):
        if not isinstance(row, list) or len(row) != n:
            cols = len(row) if isinstance(row, list) else "?"
            return f"{i + 1}행의 열 수 불일치 (기대 {n}, 실제 {cols})"
        for v in row:
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                return f"{i + 1}행에 숫자가 아닌 값 {v!r}"
    return None


def load_filters(data):
    """filters 섹션을 읽어 {N: {'Cross': 행렬, 'X': 행렬}} 형태로 돌려준다."""
    filters = {}
    raw_filters = data.get("filters") if isinstance(data, dict) else None
    if not isinstance(raw_filters, dict):
        print("✗ filters 섹션이 없거나 형식 오류 (객체 {} 형태여야 함)")
        return filters
    for size_key, group in raw_filters.items():
        m = re.fullmatch(r"size_(\d+)", str(size_key))
        if not m or not isinstance(group, dict):
            print(f"✗ {size_key}: 필터 키 형식 오류 (size_N 형태가 아님) → 건너뜀")
            continue
        n = int(m.group(1))
        loaded = {}
        for raw_label, matrix in group.items():
            label = normalize_label(raw_label)          # 'cross' → Cross, 'x' → X
            if label is None:
                print(f"✗ {size_key}: 알 수 없는 필터 라벨 {raw_label!r} → 건너뜀")
                continue
            err = check_square(matrix, n)
            if err:
                print(f"✗ {size_key} {label} 필터: {err} → 건너뜀")
                continue
            loaded[label] = matrix
        filters[n] = loaded
        print(f"✓ {size_key:<8}필터 로드 완료 ({', '.join(sorted(loaded)) or '없음'})")
    return filters


def analyze_case(key, item, filters):
    """
    패턴 1개를 분석한다. 어떤 문제가 있어도 예외로 멈추지 않고 결과 dict를 돌려준다.
    반환: {'key', 'passed'(bool), 'reason'(실패 사유 또는 '')}
    """
    def fail(reason):
        print(f"FAIL ({reason})")
        return {"key": key, "passed": False, "reason": reason}

    print(f"--- {key} ---")
    # ① 키에서 N 추출: size_13_2 → 13
    m = re.fullmatch(r"size_(\d+)_(\d+)", str(key))
    if not m:
        return fail("키 형식 오류 (size_N_idx 형태가 아님)")
    n = int(m.group(1))

    # ② 해당 크기 필터 존재 여부
    group = filters.get(n, {})
    if "Cross" not in group or "X" not in group:
        return fail(f"size_{n} 필터(Cross/X)가 없음")

    # ③ 스키마 검사: input / expected
    if not isinstance(item, dict) or "input" not in item or "expected" not in item:
        return fail("스키마 오류 (input 또는 expected 누락)")
    pattern = item["input"]
    err = check_square(pattern, n)
    if err:
        return fail(f"패턴 검증 실패 ({n}×{n} 기대) - {err}")
    expected = normalize_label(item["expected"])   # '+' → Cross, 'x' → X
    if expected is None:
        return fail(f"알 수 없는 expected 라벨 {item['expected']!r}")

    # ④ MAC 연산 + 판정
    score_c = mac(pattern, group["Cross"])
    score_x = mac(pattern, group["X"])
    result = judge(score_c, score_x, "Cross", "X")
    print(f"Cross 점수: {score_c}")
    print(f"X 점수: {score_x}")
    print(f"판정: {result} | expected: {expected} | ", end="")

    # ⑤ PASS / FAIL
    if result == expected:
        print("PASS")
        return {"key": key, "passed": True, "reason": ""}
    if result == UNDECIDED:
        return fail(f"동점 규칙 - |Cross-X| < {EPSILON} ({score_c} vs {score_x})")
    return fail(f"오판정 - 판정 {result}, expected {expected}")


def run_json_mode(path=DATA_PATH):
    print_section("[1] 필터 로드")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"✗ data.json을 읽을 수 없습니다: {e}")
        print_summary([])
        return []
    filters = load_filters(data)

    print_section("[2] 패턴 분석 (라벨 정규화 적용)")
    patterns = data.get("patterns") if isinstance(data, dict) else None
    if not isinstance(patterns, dict):
        print("✗ patterns 섹션이 없거나 형식 오류 (객체 {} 형태여야 함)")
        patterns = {}
    results = []
    for key, item in patterns.items():
        try:
            results.append(analyze_case(key, item, filters))
        except Exception as e:   # 예상 못 한 오류도 케이스 단위 FAIL로 처리 (프로그램 중단 방지)
            print(f"FAIL (예기치 못한 오류: {e})")
            results.append({"key": key, "passed": False, "reason": f"예기치 못한 오류: {e}"})

    print_section(f"[3] 성능 분석 (평균/{REPEAT}회)")
    print_perf_table(PERF_SIZES)

    print_section(f"[4] 보너스: 2차원 vs 1차원 배열 비교 (평균/{REPEAT}회)")
    print_optimization_table(PERF_SIZES)

    print_section("[5] 결과 요약")
    print_summary(results)
    return results


# ==================================================
# [5단계] 결과 요약
# ==================================================
def print_summary(results):
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed
    print(f"총 테스트: {total}개")
    print(f"통과: {passed}개")
    print(f"실패: {failed}개")
    if failed:
        print()
        print("실패 케이스:")
        for r in results:
            if not r["passed"]:
                print(f"- {r['key']}: {r['reason']}")
    print()
    print('(상세 원인 분석 및 복잡도 설명은 README.md의 "결과 리포트" 섹션 참고)')


# ==================================================
# 실행부
# ==================================================
def main():
    print("=== Mini NPU Simulator ===")
    print()
    print("[모드 선택]")
    print("1. 사용자 입력 (3x3)")
    print("2. data.json 분석")
    if ask_choice("선택") == "1":
        run_user_mode()
    else:
        run_json_mode()


if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print("\n입력이 종료되어 프로그램을 마칩니다.")
