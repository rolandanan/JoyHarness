"""Joy-Con R 按键校准脚本

交互式引导用户逐一按下 Joy-Con R 上的每个物理按键，
自动检测对应的 pygame 按钮索引和轴索引，
最终输出修正后的 constants.py 和 default.json 配置。

用法:
    python calibrate.py
"""

import sys
import json
import time
from pathlib import Path

import pygame

# 需要校准的物理按键列表（按顺序引导用户按下）
CALIBRATION_BUTTONS = [
    "A (右位)",
    "B (下位)",
    "X (上位)",
    "Y (左位)",
    "R 肩键 (顶部右侧)",
    "ZR 扳机 (顶部右下方)",
    "Plus (+) 键",
    "Home 键 (圆形)",
    "摇杆按下 (R3)",
    "SL (侧边左)",
    "SR (侧边右)",
]

def wait_for_single_press(joystick) -> set[int]:
    """等待用户按下一个或多个按钮，返回按下的按钮索引集合。

    忽略已经按住的按钮，只检测新按下的。
    """
    # 先记录当前已经按下的按钮（排除掉）
    initial: set[int] = set()
    for i in range(joystick.get_numbuttons()):
        if joystick.get_button(i):
            initial.add(i)

    while True:
        pygame.event.pump()

        current: set[int] = set()
        for i in range(joystick.get_numbuttons()):
            if joystick.get_button(i):
                current.add(i)

        new_pressed = current - initial

        # 检测到新按下且已稳定（松手了）
        if new_pressed:
            # 等待松手
            while True:
                pygame.event.pump()
                still_held: set[int] = set()
                for i in range(joystick.get_numbuttons()):
                    if joystick.get_button(i):
                        still_held.add(i)
                if not (new_pressed & still_held):
                    break
                time.sleep(0.01)
            return new_pressed

        time.sleep(0.01)


def calibrate_buttons(joystick) -> dict[str, int]:
    """交互式校准所有按钮映射。"""
    mapping: dict[str, int] = {}

    print("\n" + "=" * 50)
    print("  第一部分：按钮校准")
    print("=" * 50)
    print(f"\n控制器: {joystick.get_name()}")
    print(f"按钮数: {joystick.get_numbuttons()}, 轴数: {joystick.get_numaxes()}")
    print(f"\n请按提示逐一按下 Joy-Con R 上的按键。")
    print(f"按下后松开即可，程序会自动识别。\n")

    input("准备好了吗？按 Enter 开始...")

    used_indices: set[int] = set()

    for i, btn_name in enumerate(CALIBRATION_BUTTONS):
        while True:
            print(f"\n[{i+1}/{len(CALIBRATION_BUTTONS)}] 请按下: {btn_name}")

            pressed = wait_for_single_press(joystick)

            # 过滤已用索引
            new_indices = pressed - used_indices

            if not new_indices:
                print(f"  检测到按钮 {pressed}，但这些已经分配过了。请重试。")
                continue

            if len(new_indices) == 1:
                idx = new_indices.pop()
            else:
                print(f"  检测到多个按钮: {new_indices}，请只按一个键重试。")
                continue

            mapping[btn_name] = idx
            used_indices.add(idx)
            print(f"  -> 按钮 {btn_name} = pygame BTN {idx}")
            break

    return mapping


def calibrate_axes(joystick) -> dict[str, tuple[int, float]]:
    """校准摇杆轴映射。

    Returns:
        dict mapping direction name to (axis_index, sign)
        e.g. {"stick_right": (0, 1.0), "stick_left": (0, -1.0)}
    """
    print("\n" + "=" * 50)
    print("  第二部分：摇杆校准")
    print("=" * 50)
    print("\n现在校准摇杆方向。请按提示推动摇杆并保持。")
    print("程序检测到足够的偏移后会自动记录。\n")

    axis_map: dict[str, tuple[int, float]] = {}
    directions = [
        ("摇杆向右推到底", "right"),
        ("摇杆向左推到底", "left"),
        ("摇杆向上推到底", "up"),
        ("摇杆向下推到底", "down"),
    ]

    for prompt_text, dir_name in directions:
        print(f"\n请 {prompt_text} (保持住)...")

        # 读取轴值，等待超过阈值
        best_axis = -1
        best_val = 0.0

        while True:
            pygame.event.pump()

            for axis_idx in range(joystick.get_numaxes()):
                val = joystick.get_axis(axis_idx)
                if abs(val) > abs(best_val) and abs(val) > 0.5:
                    best_val = val
                    best_axis = axis_idx

            if best_axis >= 0 and abs(best_val) > 0.5:
                # 再确认一下稳定性
                time.sleep(0.1)
                pygame.event.pump()
                confirm_val = joystick.get_axis(best_axis)
                if abs(confirm_val) > 0.5 and (confirm_val > 0) == (best_val > 0):
                    break

            time.sleep(0.01)

        axis_map[dir_name] = (best_axis, best_val)
        print(f"  -> {dir_name}: AXIS {best_axis}, 值 {best_val:+.3f}")

        # 等待摇杆回到中心
        print("  请松开摇杆回到中心位置...")
        time.sleep(0.5)
        while True:
            pygame.event.pump()
            max_dev = 0.0
            for axis_idx in range(joystick.get_numaxes()):
                val = joystick.get_axis(axis_idx)
                max_dev = max(max_dev, abs(val))
            if max_dev < 0.15:
                break
            time.sleep(0.01)

    return axis_map


def dump_all_raw(joystick) -> None:
    """实时显示所有按钮和轴的原始值，按 Ctrl+C 退出。"""
    print("\n" + "=" * 50)
    print("  原始数据监控 (Ctrl+C 退出)")
    print("=" * 50)

    clock = pygame.time.Clock()
    prev_buttons: set[int] = set()
    button_names = {i: f"BTN_{i}" for i in range(joystick.get_numbuttons())}

    try:
        while True:
            pygame.event.pump()

            current: set[int] = set()
            for i in range(joystick.get_numbuttons()):
                if joystick.get_button(i):
                    current.add(i)

            pressed = current - prev_buttons
            released = prev_buttons - current

            for i in sorted(pressed):
                print(f"  BTN {i:2d} PRESSED  ***")
            for i in sorted(released):
                print(f"  BTN {i:2d} released")

            prev_buttons = current

            # 轴值（始终显示有偏移的）
            axis_parts = []
            for i in range(joystick.get_numaxes()):
                val = joystick.get_axis(i)
                if abs(val) > 0.2:
                    axis_parts.append(f"AXIS{i}={val:+.2f}")
            if axis_parts:
                print(f"  {', '.join(axis_parts)}")

            clock.tick(30)

    except KeyboardInterrupt:
        print("\n退出监控。")


def generate_output(
    button_mapping: dict[str, int],
    axis_map: dict[str, tuple[int, float]],
) -> None:
    """根据校准结果生成 constants.py 和 default.json。"""
    print("\n" + "=" * 50)
    print("  校准完成！生成配置文件...")
    print("=" * 50)

    # 确定 X/Y 轴索引
    right_axis, right_sign = axis_map.get("right", (0, 1.0))
    up_axis, up_sign = axis_map.get("up", (1, -1.0))

    names = ["A", "B", "X", "Y", "R", "ZR", "Plus", "Home", "RStick", "SL", "SR"]
    btn_short = {name: button_mapping[label] for name, label in zip(names, CALIBRATION_BUTTONS)}
    from src.config_loader import load_config, get_platform_config_path, save_config
    from src.device_profiles import device_key
    config = load_config(get_platform_config_path())
    identity = device_key(pygame.joystick.Joystick(_selected_index))
    config.setdefault("device_profiles", {})[identity] = {
        "buttons": {"single_right": btn_short},
        "axes": {"x": right_axis, "y": up_axis,
                 "x_sign": 1 if right_sign > 0 else -1,
                 "y_sign": -1 if up_sign > 0 else 1}}
    save_config(config)
    print("设备校准已保存，无需修改源码。推荐使用应用内设备校准。")


def main():
    print("=" * 50)
    print("  Joy-Con R 按键校准工具")
    print("=" * 50)

    pygame.init()
    pygame.joystick.init()

    count = pygame.joystick.get_count()
    if count == 0:
        print("\n未检测到手柄！请确认 Joy-Con R 已通过蓝牙连接。")
        pygame.quit()
        sys.exit(1)

    print(f"\n检测到 {count} 个手柄:")
    for i in range(count):
        js = pygame.joystick.Joystick(i)
        print(f"  [{i}] {js.get_name()} (buttons={js.get_numbuttons()}, axes={js.get_numaxes()})")

    # 选择手柄
    if count == 1:
        js_index = 0
    else:
        while True:
            try:
                raw = input(f"\n请选择手柄编号 (0-{count-1}): ")
                js_index = int(raw)
                if 0 <= js_index < count:
                    break
                print(f"  编号超出范围，请输入 0 到 {count-1} 之间的数字。")
            except ValueError:
                print("  请输入一个有效的数字。")

    global _selected_index
    _selected_index = js_index
    joystick = pygame.joystick.Joystick(js_index)
    print(f"\n使用: {joystick.get_name()}")

    # 选择模式
    print("\n请选择校准模式:")
    print("  1. 引导式校准 (推荐 — 逐个按键引导)")
    print("  2. 原始数据监控 (自由按按钮看索引)")
    print("  3. 全部执行 (先引导校准，再看原始数据)")
    choice = input("\n输入选择 (1/2/3): ").strip()

    try:
        if choice in ("1", "3"):
            button_mapping = calibrate_buttons(joystick)
            axis_map = calibrate_axes(joystick)
            generate_output(button_mapping, axis_map)

        if choice in ("2", "3"):
            dump_all_raw(joystick)

    except KeyboardInterrupt:
        print("\n\n校准中断。")
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
