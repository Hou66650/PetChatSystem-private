class Sakura {
    constructor(x, y, s, r, fn) {
        this.x = x;
        this.y = y;
        this.s = s;
        this.r = r;
        this.fn = fn;
    }

    draw(ctx) {
        ctx.save();
        ctx.translate(this.x, this.y);
        ctx.rotate(this.r);
        ctx.drawImage(document.getElementById("sakura"), 0, 0, 50 * this.s, 50 * this.s);
        ctx.restore();
    }

    update() {
        this.x = this.fn.x(this.x, this.y);
        this.y = this.fn.y(this.y, this.y);
        this.r = this.fn.r(this.r);
        if (this.x > window.innerWidth || this.x < 0 || this.y > window.innerHeight) {
            this.r = getRandom('fnr');
            this.x = getRandom('x');
            this.y = 0;
            this.s = getRandom('s');
            this.r = getRandom('r');
            this.fn = getRandom('fn');
        }
    }
}

function getRandom(option) {
    let ret, random;
    switch (option) {
        case 'x':
            ret = Math.random() * window.innerWidth;
            break;
        case 'y':
            ret = Math.random() * window.innerHeight;
            break;
        case 's':
            ret = Math.random();
            break;
        case 'r':
            ret = Math.random() * 6;
            break;
        case 'fnx':
            random = -0.5 + Math.random();
            ret = function (x, y) {
                return x + 0.5 * random - 1.7;
            };
            break;
        case 'fny':
            random = 1.5 + Math.random() * 0.7;
            ret = function (x, y) {
                return y + random;
            };
            break;
        case 'fnr':
            random = Math.random() * 0.03;
            ret = function (r) {
                return r + random;
            };
            break;
    }
    return ret;
}

function sakuraInit() {
    let canvas = document.createElement('canvas'),
        ctx = canvas.getContext('2d'),
        sakuraList = [];

    canvas.id = 'sakura-canvas';
    canvas.style.position = 'fixed';
    canvas.style.top = '0';
    canvas.style.left = '0';
    canvas.style.zIndex = '-1';
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    document.body.appendChild(canvas);

    for (let i = 0; i < 10; i++) {
        sakuraList.push(new Sakura(getRandom('x'), getRandom('y'), getRandom('s'), getRandom('r'), getRandom('fn')));
    }

    return {
        ctx: ctx,
        sakuraList: sakuraList,
        canvas: canvas
    };
}

function sakuraFlow() {
    let { ctx, sakuraList, canvas } = sakuraInit();

    function drawSakura() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        sakuraList.forEach(sakura => {
            sakura.update();
            sakura.draw(ctx);
        });
        requestAnimationFrame(drawSakura);
    }

    drawSakura();
}

document.addEventListener('DOMContentLoaded', sakuraFlow);