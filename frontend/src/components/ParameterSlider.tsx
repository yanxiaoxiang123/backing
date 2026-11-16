import { useEffect, useRef } from 'react'
import { Slider } from 'antd'
import type { SliderSingleProps } from 'antd/es/slider'

/** Keep AntD's native stepping/keyboard behavior and finish cancelled drags too. */
export function ParameterSlider(props: SliderSingleProps) {
  const active = useRef(false)
  useEffect(() => {
    const end = () => {
      active.current = false
    }
    const cancel = () => {
      if (!active.current) return
      // rc-slider listens for mouseup/touchend, but not touchcancel. Its mouseup
      // handler commits the current stepped value and removes its move listeners.
      document.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }))
      end()
    }
    window.addEventListener('blur', cancel)
    window.addEventListener('pointercancel', cancel)
    window.addEventListener('touchcancel', cancel)
    window.addEventListener('mouseup', end)
    window.addEventListener('touchend', end)
    return () => {
      cancel()
      window.removeEventListener('blur', cancel)
      window.removeEventListener('pointercancel', cancel)
      window.removeEventListener('touchcancel', cancel)
      window.removeEventListener('mouseup', end)
      window.removeEventListener('touchend', end)
    }
  }, [])
  return (
    <div
      className="parameter-slider"
      onMouseDownCapture={() => (active.current = true)}
      onTouchStartCapture={() => (active.current = true)}
    >
      <Slider {...props} />
    </div>
  )
}
