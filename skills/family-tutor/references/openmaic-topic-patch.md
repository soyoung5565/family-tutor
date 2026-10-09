# Patch: OpenMAIC 接收 ?topic=xxx URL参数

## 文件: D:\projects\OpenMAIC\app\page.tsx

### 1. 添加 import
```typescript
import { useRouter, useSearchParams } from 'next/navigation';
```

### 2. 添加 hook (在 `const router = useRouter();` 之后)
```typescript
const searchParams = useSearchParams();
```

### 3. 添加 URL参数读取 (在 draft restore effect 之后)
```typescript
// Read ?topic= from URL and auto-fill + auto-submit
const topicAppliedRef = useRef(false);
/* eslint-disable react-hooks/set-state-in-effect -- Hydrate topic from URL param */
useEffect(() => {
  if (topicAppliedRef.current) return;
  const topic = searchParams.get('topic');
  if (!topic) return;
  topicAppliedRef.current = true;
  setForm((prev) => ({ ...prev, requirement: topic }));
  setTimeout(() => {
    const btn = document.querySelector('[data-generate-button]') as HTMLButtonElement | null;
    if (btn && !btn.disabled) btn.click();
  }, 800);
}, [searchParams]);
/* eslint-enable react-hooks/set-state-in-effect */
```

### 4. 给生成按钮添加属性
在 `<button onClick={handleGenerate}` 之前添加 `data-generate-button`
