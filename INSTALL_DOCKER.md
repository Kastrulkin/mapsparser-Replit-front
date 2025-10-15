# 🐳 Установка Docker

## macOS

### 1. Установка через Homebrew (рекомендуется)
```bash
# Установить Homebrew (если не установлен)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Установить Docker
brew install --cask docker
```

### 2. Установка через официальный сайт
1. Перейдите на https://www.docker.com/products/docker-desktop/
2. Скачайте Docker Desktop для macOS
3. Установите .dmg файл
4. Запустите Docker Desktop

### 3. Проверка установки
```bash
docker --version
docker-compose --version
```

## Linux (Ubuntu/Debian)

```bash
# Обновить пакеты
sudo apt update

# Установить зависимости
sudo apt install apt-transport-https ca-certificates curl gnupg lsb-release

# Добавить GPG ключ Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Добавить репозиторий Docker
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Установить Docker
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Добавить пользователя в группу docker
sudo usermod -aG docker $USER

# Перезайти в систему или выполнить
newgrp docker
```

## Windows

1. Скачайте Docker Desktop с https://www.docker.com/products/docker-desktop/
2. Установите Docker Desktop
3. Перезагрузите компьютер
4. Запустите Docker Desktop

## 🚀 После установки

### Проверка работы
```bash
# Проверить версию
docker --version

# Проверить Docker Compose
docker compose version

# Запустить тестовый контейнер
docker run hello-world
```

### Запуск нашего проекта
```bash
# Перейти в папку проекта
cd "/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/AI bots/SEO с Реплит на Курсоре"

# Собрать образ
./docker-run.sh build

# Запустить приложение
./docker-run.sh up
```

## 🔧 Альтернатива: Docker без установки

Если не хотите устанавливать Docker локально, можете:

1. **Использовать GitHub Codespaces** (бесплатно для публичных репозиториев)
2. **Использовать Replit** с Docker поддержкой
3. **Развернуть на VPS** с предустановленным Docker

### Развёртывание на VPS с Docker
```bash
# На сервере
sudo apt update
sudo apt install docker.io docker-compose
sudo systemctl start docker
sudo systemctl enable docker

# Клонировать проект
git clone <your-repo>
cd project

# Запустить
./docker-run.sh build
./docker-run.sh up
```

## 🆘 Решение проблем

### Docker не запускается на macOS
```bash
# Перезапустить Docker Desktop
# Или через терминал
sudo /Applications/Docker.app/Contents/MacOS/Docker --uninstall
sudo /Applications/Docker.app/Contents/MacOS/install --install-required-packages
```

### Проблемы с правами на Linux
```bash
# Добавить пользователя в группу docker
sudo usermod -aG docker $USER
newgrp docker

# Или запускать с sudo
sudo docker-compose up
```

### Очистка Docker
```bash
# Удалить неиспользуемые образы
docker system prune -a

# Удалить все контейнеры
docker container prune -a
```
