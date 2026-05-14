from datetime import datetime
from dateutil.relativedelta import relativedelta

# 当前日期：2026年5月12日
current_date = datetime(2026, 5, 12)

# 获取用户输入的出生年月日
birth_input = input("请输入您的出生年月日（格式：YYYY-MM-DD）：")

try:
    # 解析出生日期
    birth_date = datetime.strptime(birth_input, "%Y-%m-%d")

    # 计算生存天数
    survival_days = (current_date - birth_date).days

    # 计算年龄
    age = current_date.year - birth_date.year - ((current_date.month, current_date.day) < (birth_date.month, birth_date.day))

    # 计算18岁生日
    eighteenth_birthday = birth_date + relativedelta(years=18)

    print(f"您的年龄是：{age} 岁")
    print(f"您的生存天数是：{survival_days} 天")

    if age >= 18:
        print("你已经成年了，欢迎来到成人世界")
    else:
        # 计算到18岁的剩余时间
        remaining = relativedelta(eighteenth_birthday, current_date)
        remaining_years = remaining.years
        remaining_days = remaining.days  # 这只是月内天数差，需要调整为总天数

        # 更准确地计算总剩余天数
        total_remaining_days = (eighteenth_birthday - current_date).days
        remaining_years = total_remaining_days // 365
        remaining_days = total_remaining_days % 365

        print(f"你还未成年哦，还有 {remaining_years} 年 {remaining_days} 天你才成年")

except ValueError:
    print("输入格式错误，请使用 YYYY-MM-DD 格式输入出生年月日。")
