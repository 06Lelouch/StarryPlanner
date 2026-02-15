"""One-command build script: python build.py"""
import subprocess
import sys

def main():
    print("Building AI Scheduler .exe ...")
    result = subprocess.run(
        [sys.executable, '-m', 'PyInstaller', 'ai_scheduler.spec', '--noconfirm'],
        cwd=__file__ and __import__('os').path.dirname(__import__('os').path.abspath(__file__)),
    )
    if result.returncode == 0:
        print("\nBuild complete!  ->  dist/AIScheduler/AIScheduler.exe")
    else:
        print("\nBuild failed. Check the output above for errors.")
    sys.exit(result.returncode)

if __name__ == '__main__':
    main()
