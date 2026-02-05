# 기억해두면 좋은 docker 명령문들

## 목적

배포하면서 사용했던 명령문들을 정리하기 위함

## docker 컨테이너 목록
- 현재 실행되는 컨테이너들의 목록을 확인
  ```
  docker ps
  ```

- 실행되지 않는 컨테이너까지 포함하여 목록을 확인
  ```
  docker ps -a
  ```

## docker 모든 이미지를 새로 빌드하여 컨테이너를 생성
```
docker-compose up -d --build
```

## 엉뚱한 브랜치에서 작업 중일 때 해당 작업물을 날리지 않고 다른 브랜치로 넘기는 방법
```
git stash
git stash save
git stash apply
```