# M1 수동 샘플 이미지

이 폴더는 M1 Image Ingestion & Artifact Storage 작업을 수동으로 확인할 때 쓰는 실제 샘플 이미지입니다.

- `problem.png`: 원본 문제 이미지입니다. 파일명은 `.png`지만 실제 파일 내용은 JPEG입니다.
- `teacher_solution.png`: 같은 문제의 선생님 손글씨 풀이 이미지입니다.
- `output_example.png`: 기대 출력 예시입니다.

M1 자동 테스트는 이 파일을 직접 사용하지 않고, MIME/magic byte 계약을 안정적으로 검증하기 위해 테스트 내부의 synthetic PNG/JPEG bytes를 사용합니다.
