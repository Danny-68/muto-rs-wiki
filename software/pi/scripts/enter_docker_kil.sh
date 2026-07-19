#!/bin/bash

# 镜像名称
IMAGE_NAME="kilted:1.1"

# 获取基于该镜像运行的容器ID
CONTAINER_ID=$(docker ps --filter "ancestor=$IMAGE_NAME" --format "{{.ID}}" | head -n 1)

# 检查是否找到容器
if [ -z "$CONTAINER_ID" ]; then
    echo "错误：未找到基于镜像 $IMAGE_NAME 运行的容器！"
    echo "请确保容器正在运行，可以使用 'docker ps' 查看运行中的容器。"
    exit 1
fi

# 进入容器的 /bin/bash
echo "正在进入容器 $CONTAINER_ID 的终端..."
docker exec -it "$CONTAINER_ID" /bin/bash
