from tasks import open_webpage

if __name__ == '__main__':
    result = open_webpage.delay()
    print(f"ID задачи: {result.id}")
