class Solution:
    def isValid(self, s: str) -> bool:
        opener = {")": "(", "]": "[", "}": "{"}
        stack: list[str] = []
        for c in s:
            if c in opener:
                if not stack or stack.pop() != opener[c]:
                    return False
            else:
                stack.append(c)
        return not stack
