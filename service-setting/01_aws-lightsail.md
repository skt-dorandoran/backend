# AWS Lightsail 서버 세팅

## 목적

클라우드 기반 Ubuntu 서버 초기 구축 및 운영 환경 준비

## 인스턴스 생성
- 인스턴스 위치: 서울, 영역 A (ap-northeast-2a)
- 이미지: Linux, OS 전용, Ubuntu 24.04 LTS
- 인스턴스 플랜: $12/month
  - RAM: `2GB, Swap 6GB 할당 필요`
  - CPU: vCPU x 2
  - Storage: 600GB SSD
  - Traffic: 3TB/month (Upload/Download 합산)

### 추가 설정
- 인스턴스 고정 IP 설정
- 방화벽 설정 (아웃바운드 포트 개방)
- 아이피-도메인 설정
  - `duckdns.org` 기반의 `dorandoran.duckdns.org` 무료 도메인 연결

## 서버 접속
```
ssh ubuntu@dorandoran.duckdns.org -i team-dorandoran.pem
```

- 서버 접속은 ssh key가 존재하는 위치에서 CMD/Powershell에 접속한 뒤 접속하면 됨
- ssh key는 호스팅 사이트에서 획득 또는 관리자에서 발급을 받아야 함
- ssh key 접속 시 문제 해결
  - Windows에서 `Permission denied (publickey).` 오류 발생 시
    - https://blog.naver.com/dae0park/223134057314 참고
  - Ubuntu에서 `Permission denied (publickey).` 오류 발생 시
    ```
    sudo chmod 400 ./team-dorandoran.pem
    ```

## 서버 세팅

### 우분투 서버의 시간을 한국 표준시로 변경 (KST)
- AWS의 Ubuntu는 기본적으로 UTC+0으로 설정되어 있음
  ```
  sudo timedatectl set-timezone Asia/Seoul
  ```
- 변경된 시간을 확인하기 위해 다음 명령어를 활용
  ```
  date
  ```

### 미러 서버를 카카오 서버로 변경
- 패키지를 다운받을 때, 기본 서버가 *.ubuntu.com 이라는 해외 서버이기 때문에, 국내망을 이용할 수 있는 카카오 미러서버를 사용
  - 해외망, 해외 서버를 사용하게 되면 패키지를 갱신/다운로드를 하는 속도가 매우 느리기 때문
  - AWS EC2 혹은 AWS Lightsail에서 사용할 수 있다
    - 타 Ubuntu 서버를 사용할 경우 [ap-northeast-2.ec2.archive.ubuntu.com](http://ap-northeast-2.ec2.archive.ubuntu.com) 부분을 “sudo vi /etc/apt/sources.list”으로 확인해서 다른 서버로 변경 후 사용할 것
- Ubuntu 24.04 LTS인 경우
  ```
  sudo sed -i 's/ap-northeast-2.ec2.archive.ubuntu.com/mirror.kakao.com/g' /etc/apt/sources.list.d/ubuntu.sources
  ```
- Ubuntu 22.04 LTS 혹은 그 이하인 경우
  ```
  sudo sed -i 's/ap-northeast-2.ec2.archive.ubuntu.com/mirror.kakao.com/g' /etc/apt/sources.list
  ```

### 패키지 목록 업데이트 및 패키지 업데이트
- 패키지를 다운받는 미러서버의 주소가 변경되었기 때문에, update를 진행한다
- 패키지 목록 업데이트
  ```
  sudo apt-get -y update
  ```
- 최신 패키지로 업그레이드
  - Ubuntu 24.04 LTS인 경우
    ```
    sudo apt-get -y upgrade
    ```
  - Ubuntu 22.04 LTS 혹은 그 이하인 경우
    ```
    sudo apt-get --yes --force-yes -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" dist-upgrade
    ```
- 사용하지 않는 종속 패키지 제거
  ```
  sudo apt-get -y autoremove --purge
  ```
- 기타 오류 대처방법
  - 패키지 목록 업데이트 도중 다음과 같은 문구가 나오면 `ENTER` 키를 누른다.
  ```
  What do you want to do about modified configuration file sshd_config?
  ```
  - `E: The repository '[http://ppa.launchpad.net/certbot/certbot/ubuntu](http://ppa.launchpad.net/certbot/certbot/ubuntu) focal Release' does not have a Release file.` 오류 발생시 해결 방법
  ```
  sudo apt-add-repository -y -r ppa:certbot/certbot
  ```
  - `E: Package 'python-certbot-nginx' has no installation candidate` 오류 발생시 해결 방법
  ```
  sudo apt-get -y install python3-certbot-nginx
  ```

### Swap 영역 할당
- 기본적인 RAM의 용량이 작기 때문에, SSD의 남은 용량을 가상 메모리(Swap) 영역으로 일부 할당
- 용량 확인
  ```
  free -h
  ```
- 스왑 영역 할당 (예: 4GB)
  ```
  sudo fallocate -l 4G /swapfile
  ```
- swapfile 권한 수정
  ```
  sudo chmod 600 /swapfile
  ```
- swapfile 생성
  ```
  sudo mkswap /swapfile
  ```
- swapfile 활성화
  ```
  sudo swapon /swapfile
  ```
- 시스템이 재부팅 되어도 swap 유지할 수 있도록 설정
  ```
  sudo echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
  ```
- swap 영역이 할당 되었는지 확인
  ```
  free -h
  ```

### 시스템 상태 확인
- htop
  ```
  sudo apt-get -y install htop
  ```
- btop
  ```
  sudo apt-get -y install btop
  ```