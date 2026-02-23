# Principles — mdn-animation

- generated_at: 2026-02-23T17:46:01Z
- source_url: https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_animations/Using_CSS_animations

- This lets you configure the timing, duration, and other details of how the animation sequence should progress.
- Specifies the delay between an element loading and the start of an animation sequence and whether the animation should start immediately from its beginning or partway through the animation.
- Specifies whether an animation's first iteration should be forward or backward and whether subsequent iterations should alternate direction on each run through the sequence or reset to the start point and repeat.
- Specifies the number of times an animation should repeat.
- Each keyframe describes how the animated element should render at a given time during the animation sequence.
- element specifies that the animation should take 3 seconds to execute from start to finish, using the
- This tells the browser the name should be normal for the first and last 25% of the animation, but turn pink while being scaled up and back again in the middle.
- This behavior is useful for creating entry/exit animations where you want to for example remove a container from the DOM with
- to use when multiple animations affect the same property simultaneously.
- Specifies whether to pause or play an animation sequence.
- Specifies the timeline that is used to control the progress of a CSS animation.
- Since the timing of the animation is defined in the CSS style that configures the animation, keyframes use a
- This feature can be used when you want to apply multiple animations in a single rule and set different durations, iteration counts, etc., for each of the animations.
- values, then the extra or unused animation property values, in this case, two
- This causes the first frame of the animation to have the header drawn off the right edge of the browser window.
- This causes the header to finish its animation in its default state, flush against the left edge of the content area.
- You can get additional control over animations — as well as useful information about them — by making use of animation events.
- object, can be used to detect when animations start, finish, and begin a new iteration.
- We'll use JavaScript code to listen for all three possible animation events.
- This example shows how to use CSS animations to make <code>H1</code>
