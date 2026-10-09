import turtle
colors = ['red', 'orange', 'yellow', 'green', 'blue', 'indigo', 'violet']
turtle.bgcolor('black')
turtle.speed(0)
turtle.width(2)
for i in range(360):
    turtle.pencolor(colors[i % len(colors)])
    turtle.forward(i * 2)
    turtle.left(59)
    turtle.done()