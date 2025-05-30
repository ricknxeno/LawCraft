class Snake {
    constructor(board) {
        this.board = board;
    }

    animate(startCell, endCell, callback) {
        const snakeGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
        const start = this.board.getCellCenter(startCell);
        const end = this.board.getCellCenter(endCell);
        
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        const dx = end.x - start.x;
        const dy = end.y - start.y;
        const distance = Math.sqrt(dx * dx + dy * dy);
        
        const numCurves = Math.ceil(distance / 100);
        let pathData = `M ${start.x},${start.y}`;
        
        for (let i = 0; i < numCurves; i++) {
            const t1 = (i + 0.5) / numCurves;
            const t2 = (i + 1) / numCurves;
            
            const midX = start.x + dx * t1;
            const midY = start.y + dy * t1;
            const endX = start.x + dx * t2;
            const endY = start.y + dy * t2;
            
            const offset = 30 * Math.sin(i * Math.PI);
            pathData += ` Q ${midX + offset},${midY} ${endX},${endY}`;
        }
        
        path.setAttribute("class", "snake-body");
        path.setAttribute("d", pathData);
        
        const headGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
        headGroup.innerHTML = `
            <path class="snake-head" d="M -30,0 C -10,-20 10,-20 30,0 C 10,20 -10,20 -30,0 Z"/>
            <circle cx="16" cy="-6" r="4" fill="black"/>
            <circle cx="16" cy="6" r="4" fill="black"/>
            <circle cx="17" cy="-7" r="1.5" fill="white"/>
            <circle cx="17" cy="5" r="1.5" fill="white"/>
            <path class="snake-tongue" d="M 30,0 L 44,0 L 50,-6 M 44,0 L 50,6"/>
        `;
        
        snakeGroup.appendChild(path);
        snakeGroup.appendChild(headGroup);
        this.board.players.parentNode.insertBefore(snakeGroup, this.board.players);
        
        const pathLength = path.getTotalLength();
        let animationStart = null;
        const duration = 1500;
        
        const animate = (timestamp) => {
            if (!animationStart) animationStart = timestamp;
            const progress = (timestamp - animationStart) / duration;
            
            if (progress <= 1) {
                const point = path.getPointAtLength(pathLength * progress);
                const nextPoint = path.getPointAtLength(Math.min(pathLength, pathLength * progress + 1));
                const angle = Math.atan2(nextPoint.y - point.y, nextPoint.x - point.x) * 180 / Math.PI;
                
                headGroup.setAttribute('transform', 
                    `translate(${point.x},${point.y}) rotate(${angle})`);
                
                requestAnimationFrame(animate);
            } else {
                snakeGroup.remove();
                if (callback) callback();
            }
        };
        
        requestAnimationFrame(animate);
    }
}

class Ladder {
    constructor(board) {
        this.board = board;
    }

    animate(startCell, endCell, callback) {
        const ladderGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
        const start = this.board.getCellCenter(startCell);
        const end = this.board.getCellCenter(endCell);
        
        const dx = end.x - start.x;
        const dy = end.y - start.y;
        const angle = Math.atan2(dy, dx);
        const length = Math.sqrt(dx * dx + dy * dy);
        const numRungs = Math.floor(length / 40);
        const railOffset = 15;
        
        // Draw rails with curve
        const midX = (start.x + end.x) / 2;
        const midY = (start.y + end.y) / 2 - 40; // Add some curve
        
        const path1 = `M ${start.x - railOffset * Math.sin(angle)} ${start.y + railOffset * Math.cos(angle)} 
                       Q ${midX - railOffset * Math.sin(angle)} ${midY + railOffset * Math.cos(angle)} 
                       ${end.x - railOffset * Math.sin(angle)} ${end.y + railOffset * Math.cos(angle)}`;
                       
        const path2 = `M ${start.x + railOffset * Math.sin(angle)} ${start.y - railOffset * Math.cos(angle)} 
                       Q ${midX + railOffset * Math.sin(angle)} ${midY - railOffset * Math.cos(angle)} 
                       ${end.x + railOffset * Math.sin(angle)} ${end.y - railOffset * Math.cos(angle)}`;
        
        const rail1 = document.createElementNS("http://www.w3.org/2000/svg", "path");
        const rail2 = document.createElementNS("http://www.w3.org/2000/svg", "path");
        
        rail1.setAttribute("d", path1);
        rail2.setAttribute("d", path2);
        rail1.setAttribute("class", "ladder");
        rail2.setAttribute("class", "ladder");
        
        ladderGroup.appendChild(rail1);
        ladderGroup.appendChild(rail2);
        
        // Draw rungs
        for (let i = 0; i <= numRungs; i++) {
            const t = i / numRungs;
            const x = start.x + dx * t;
            const y = start.y + dy * t - Math.sin(Math.PI * t) * 40; // Add curve to rungs
            
            const rung = document.createElementNS("http://www.w3.org/2000/svg", "line");
            const localAngle = Math.atan2(
                (end.y - start.y) / numRungs,
                (end.x - start.x) / numRungs
            );
            
            rung.setAttribute("x1", x - railOffset * Math.sin(localAngle));
            rung.setAttribute("y1", y + railOffset * Math.cos(localAngle));
            rung.setAttribute("x2", x + railOffset * Math.sin(localAngle));
            rung.setAttribute("y2", y - railOffset * Math.cos(localAngle));
            rung.setAttribute("class", "ladder-rung");
            
            ladderGroup.appendChild(rung);
        }
        
        this.board.players.parentNode.insertBefore(ladderGroup, this.board.players);
        
        // Animate climber
        const climber = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        climber.setAttribute("class", "climber");
        climber.setAttribute("r", "10");
        ladderGroup.appendChild(climber);
        
        let animationStart = null;
        const duration = 1500;
        
        const animate = (timestamp) => {
            if (!animationStart) animationStart = timestamp;
            const progress = (timestamp - animationStart) / duration;
            
            if (progress <= 1) {
                const x = start.x + dx * progress;
                const y = start.y + dy * progress;
                climber.setAttribute("cx", x);
                climber.setAttribute("cy", y);
                requestAnimationFrame(animate);
            } else {
                ladderGroup.remove();
                if (callback) callback();
            }
        };
        
        requestAnimationFrame(animate);
    }
}

class GameBoard {
    constructor() {
        this.cellSize = 60;
        this.gridSize = 10;
        this.boardGrid = document.getElementById('boardGrid');
        this.players = document.getElementById('players');
        
        this.snakes = {
            99: 41,
            89: 53,
            76: 58,
            66: 45,
            54: 31,
            43: 18,
            27: 5,
            97: 78,
            87: 24,
            64: 60,
            50: 34,
            48: 26,
            44: 22,
            39: 3,
            33: 9,
            29: 11,
            25: 2,
            21: 1,
            19: 7,
            17: 4,
            15: 6
        };
        
        this.ladders = {
            3: 51,
            8: 26,
            28: 46,
            40: 82,
            52: 68,
            65: 85,
            11: 49,
            2: 38,
            7: 14,
            10: 29,
            22: 37,
            30: 44,
            36: 48,
            42: 59,
            49: 67,
            55: 76,
            62: 81,
            69: 91,
            72: 93,
            78: 98,
            84: 95
        };
        
        this.init();
        this.setupEventListeners();
    }

    init() {
        this.createBoard();
        this.createPlayer();
    }

    createBoard() {
        for (let row = 0; row < this.gridSize; row++) {
            for (let col = 0; col < this.gridSize; col++) {
                const cellNumber = (this.gridSize - 1 - row) * this.gridSize + col + 1;
                const x = col * this.cellSize;
                const y = row * this.cellSize;
                
                const cell = document.createElementNS("http://www.w3.org/2000/svg", "rect");
                cell.setAttribute("x", x);
                cell.setAttribute("y", y);
                cell.setAttribute("width", this.cellSize);
                cell.setAttribute("height", this.cellSize);
                
                if (this.snakes[cellNumber]) {
                    cell.setAttribute("class", "board-cell snake-cell");
                } else if (this.ladders[cellNumber]) {
                    cell.setAttribute("class", "board-cell ladder-cell");
                } else {
                    cell.setAttribute("class", "board-cell");
                }
                
                const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
                text.setAttribute("x", x + 10);
                text.setAttribute("y", y + 25);
                text.setAttribute("class", "cell-number");
                text.textContent = cellNumber;
                
                this.boardGrid.appendChild(cell);
                this.boardGrid.appendChild(text);
            }
        }
    }

    createPlayer() {
        const player = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        player.setAttribute("class", "player-token");
        player.setAttribute("r", "15");
        player.dataset.position = 1;
        
        const startPos = this.getCellCenter(1);
        player.setAttribute("cx", startPos.x);
        player.setAttribute("cy", startPos.y);
        
        this.players.appendChild(player);
    }

    setupEventListeners() {
        document.getElementById('rollDice').addEventListener('click', () => {
            const roll = Math.floor(Math.random() * 6) + 1;
            console.log(`Rolled: ${roll}`);
            const player = this.players.querySelector('.player-token');
            const currentPosition = parseInt(player.dataset.position || 1);
            const targetPosition = Math.min(currentPosition + roll, 100);
            
            this.animatePlayerMovement(player, currentPosition, targetPosition, () => {
                console.log(`Moved to: ${targetPosition}`);
                this.checkForSnakesOrLadders(player, targetPosition);
            });
        });
    }

    checkForSnakesOrLadders(player, position) {
        if (this.snakes[position]) {
            console.log(`Snake from ${position} to ${this.snakes[position]}`);
            setTimeout(() => {
                const snake = new Snake(this);
                snake.animate(position, this.snakes[position], () => {
                    this.movePlayer(player, this.snakes[position]);
                    player.dataset.position = this.snakes[position];
                });
            }, 200);
        } else if (this.ladders[position]) {
            console.log(`Ladder from ${position} to ${this.ladders[position]}`);
            setTimeout(() => {
                const ladder = new Ladder(this);
                ladder.animate(position, this.ladders[position], () => {
                    this.movePlayer(player, this.ladders[position]);
                    player.dataset.position = this.ladders[position];
                });
            }, 200);
        } else {
            player.dataset.position = position;
        }
    }

    animatePlayerMovement(player, start, end, callback) {
        let current = start;
        const moveNext = () => {
            if (current < end) {
                current++;
                this.movePlayer(player, current);
                setTimeout(moveNext, 200);
            } else {
                if (callback) callback();
            }
        };
        moveNext();
    }

    movePlayer(player, position) {
        const pos = this.getCellCenter(position);
        player.setAttribute("cx", pos.x);
        player.setAttribute("cy", pos.y);
    }

    getCellCenter(cellNumber) {
        const row = Math.floor((cellNumber - 1) / this.gridSize);
        const col = (cellNumber - 1) % this.gridSize;
        const x = col * this.cellSize + this.cellSize / 2;
        const y = (this.gridSize - 1 - row) * this.cellSize + this.cellSize / 2;
        return { x, y };
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new GameBoard();
});


