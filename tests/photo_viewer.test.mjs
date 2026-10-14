import assert from 'node:assert/strict';
import test from 'node:test';
import PhotoViewer from '../lotoshino/static/js/photo_viewer.js';

function viewer() {
    const captures = new Set();
    const attributes = {};
    const instance = Object.create(PhotoViewer.prototype);
    Object.assign(instance, {
        image: { style: {}, getAnimations: () => [] },
        baseWidth: 500, baseHeight: 400, scale: 1, pan: { x: 0, y: 0 },
        pointers: new Map(), dialog: { open: true },
        zoomButton: { setAttribute: (key, value) => { attributes[key] = value; } },
        canvas: {
            clientWidth: 500, clientHeight: 400, dataset: {},
            getBoundingClientRect: () => ({ left: 0, top: 0, right: 500, bottom: 400, width: 500, height: 400 }),
            contains: target => target === 'canvas',
            setPointerCapture: id => captures.add(id),
            hasPointerCapture: id => captures.has(id),
            releasePointerCapture: id => captures.delete(id),
        },
        steps: [], step: direction => instance.steps.push(direction),
    });
    return { instance, captures, attributes };
}

const pointer = (pointerId, clientX, clientY = 200) => ({
    pointerId, clientX, clientY, button: 0, isPrimary: pointerId === 1, pointerType: 'touch',
});
function event(extra = {}) {
    return { clientX: 250, clientY: 200, target: 'canvas', deltaY: -Math.log(2) * 100,
        deltaMode: 0, ctrlKey: true, prevented: false,
        preventDefault() { this.prevented = true; }, ...extra };
}

// Exercise the real interaction methods; the fixture only substitutes layout and DOM IO.
test('two fingers zoom about their midpoint; remaining finger pans without jumping', () => {
    const { instance: v, captures } = viewer();
    v.pointerDown(pointer(1, 200));
    v.pointerDown(pointer(2, 300)); // A non-primary pointer must not be discarded.
    v.pointerMove(pointer(2, 400));
    assert.equal(v.scale, 2);
    assert.deepEqual(v.pan, { x: 50, y: 0 });
    v.pointerUp(pointer(2, 400));
    v.pointerMove(pointer(1, 210));
    assert.deepEqual(v.pan, { x: 60, y: 0 });
    v.pointerUp(pointer(1, 210));
    assert.equal(captures.size, 0);
    assert.deepEqual(v.steps, []);
});

test('pinch has bounded zoom and cannot accidentally advance the gallery when released', () => {
    const { instance: v, attributes } = viewer();
    v.pointerDown(pointer(1, 100));
    v.pointerDown(pointer(2, 200));
    v.pointerMove(pointer(2, 2000));
    assert.equal(v.scale, 8);
    v.pointerMove(pointer(2, 101));
    assert.equal(v.scale, 1);
    assert.equal(Math.abs(v.pan.x) + Math.abs(v.pan.y), 0);
    assert.equal(attributes['aria-pressed'], 'false');
    v.pointerUp(pointer(2, 101));
    v.pointerUp(pointer(1, 300));
    assert.deepEqual(v.steps, []);
});

test('single pointer swipes still navigate; cancellation clears all pointer capture', () => {
    const { instance: v, captures } = viewer();
    v.pointerDown(pointer(1, 100));
    v.pointerUp(pointer(1, 200));
    assert.deepEqual(v.steps, [-1]);
    v.pointerDown(pointer(1, 100));
    v.pointerDown(pointer(2, 200));
    v.cancelGesture();
    assert.equal(captures.size, 0);
    assert.equal(v.pointers.size, 0);
    assert.equal(v.gesture, null);
    v.pointerMove(pointer(2, 400));
    assert.equal(v.scale, 1);
});

test('trackpad wheel cancels browser zoom and preserves the image point under the cursor', () => {
    const { instance: v } = viewer();
    const e = event({ clientX: 100, clientY: 100 });
    v.wheelZoom(e);
    assert.equal(e.prevented, true);
    assert.equal(v.scale, 2);
    // At scale 1 the local image point is (-150,-100). It remains at (100,100).
    assert.equal(250 + v.pan.x - 150 * v.scale, 100);
    assert.equal(200 + v.pan.y - 100 * v.scale, 100);
    assert.match(v.image.style.transform, /scale\(2\)/);
});

test('wheel handling stays inside the open viewer and preserves caption scrolling', () => {
    const { instance: v } = viewer();
    const scroll = event({ ctrlKey: false, target: 'caption' });
    v.wheelZoom(scroll);
    assert.equal(scroll.prevented, false);
    v.dialog.open = false;
    const closed = event();
    v.wheelZoom(closed);
    assert.equal(closed.prevented, false);
    assert.equal(v.scale, 1);
    v.dialog.open = true;
    v.image = null;
    const loading = event();
    v.wheelZoom(loading);
    assert.equal(loading.prevented, true);
    assert.equal(v.scale, 1);
});

test('Safari gesture stream zooms once even if accompanied by wheel events', () => {
    const { instance: v } = viewer();
    const start = event({ type: 'gesturestart', scale: 1 });
    v.nativePinch(start);
    assert.equal(start.prevented, true);
    v.nativePinch(event({ type: 'gesturechange', scale: 2 }));
    assert.equal(v.scale, 2);
    const wheel = event();
    v.wheelZoom(wheel);
    assert.equal(wheel.prevented, true);
    assert.equal(v.scale, 2);
    v.nativePinch(event({ type: 'gestureend' }));
    assert.equal(v.nativeGesture, null);
});

test('touch pointers take precedence over duplicate Safari gesture events', () => {
    const { instance: v } = viewer();
    v.pointerDown(pointer(1, 200));
    v.pointerDown(pointer(2, 300));
    v.nativePinch(event({ type: 'gesturestart', scale: 1 }));
    v.pointerMove(pointer(2, 400));
    v.nativePinch(event({ type: 'gesturechange', scale: 3 }));
    assert.equal(v.scale, 2);
    v.pointerUp(pointer(2, 400));
    v.nativePinch(event({ type: 'gesturechange', scale: 3 }));
    assert.equal(v.scale, 2);
});

test('invalid scale cannot poison transforms; panning is confined to image bounds', () => {
    const { instance: v } = viewer();
    v.zoomAt(NaN, { x: 10, y: 20 });
    assert.equal(v.scale, 1);
    v.zoomAt(2, { x: 250, y: 200 });
    v.pointerDown(pointer(1, 250));
    v.pointerMove(pointer(1, 3000, -3000));
    assert.deepEqual(v.pan, { x: 250, y: -200 });
});
