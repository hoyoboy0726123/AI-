import time
from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig

config = SO101FollowerConfig(
    port="COM3",                   # 換成 A-06 找到的連接埠
    id="my_awesome_follower_arm",  # 和 A-16 校準時用同一個名字
    max_relative_target=5.0,       # 每次最多動 5，一定要寫成小數
)
robot = SO101Follower(config)
robot.connect()
try:
    obs = robot.get_observation()
    for name, value in obs.items():
        print(name, round(value, 1))
    action = {k: v for k, v in obs.items() if k.endswith(".pos")}
    for target in (50.0, 20.0):    # 夾爪 0 到 100，先到 50 再到 20
        action["gripper.pos"] = target
        for _ in range(20):
            robot.send_action(action)
            time.sleep(0.05)
    print("負載讀數:", robot.bus.sync_read("Present_Load"))
finally:
    robot.disconnect()
