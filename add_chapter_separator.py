import re

def add_separator_before_chapters(input_file, output_file=None):
    """
    在包含“第X章”的行前面插入“||||”
    
    Args:
        input_file: 输入的txt文件路径
        output_file: 输出的txt文件路径（如果为None，则覆盖原文件）
    """
    # 读取原文件内容
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 处理每一行
    new_lines = []
    for line in lines:
        # 匹配“第X章”的模式（X可以是数字或中文数字）
        if re.match(r'^\s*第[零一二三四五六七八九十百千万\d]+章', line):
            new_lines.append('||||\n')  # 添加分隔符
        new_lines.append(line)
    
    # 写入文件
    output_path = output_file if output_file else input_file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print(f"处理完成！已处理文件：{output_path}")

# 使用示例
if __name__ == "__main__":
    # 方式1：直接修改原文件
    add_separator_before_chapters("成稿.txt")
    
    # 方式2：另存为新文件
    # add_separator_before_chapters("输入.txt", "输出.txt")