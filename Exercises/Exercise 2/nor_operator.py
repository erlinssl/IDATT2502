import numpy as np
import torch
import matplotlib.pyplot as plt

x_train = torch.Tensor([[0., 0.], [0., 1.], [1., 0.], [1., 1.]])
y_train = torch.Tensor([[1.], [0.], [0.], [0.]])


def sigmoid_function(z):
    return 1 / (1 + np.e ** -z)


class NorModel:
    def __init__(self):
        self.W = torch.tensor([[-1.0], [-1.0]], requires_grad=True)
        self.b = torch.tensor([[1.0]], requires_grad=True)

    def f(self, x):
        return sigmoid_function(torch.Tensor(x) @ self.W + self.b)

    def loss(self, x, y):
        return -torch.mean(y * torch.log(self.f(x)) + (1 - y) * torch.log(1 - self.f(x)))


model = NorModel()

optimizer = torch.optim.SGD([model.W, model.b], 1)
for epoch in range(10000):
    model.loss(x_train, y_train).backward()
    optimizer.step()
    optimizer.zero_grad()

fig = plt.figure('NOR operator')
fig.suptitle('NOR operator')
plot = fig.add_subplot(111, projection='3d')
plot.set_xlabel('$x_1$')
plot.set_ylabel('$x_2$')
plot.set_zlabel('y')
plot.set_xticks([0, 1])
plot.set_yticks([0, 1])
plot.set_zticks([0, 1])
plot.set_xlim(-0.25, 1.25)
plot.set_ylim(-0.25, 1.25)
plot.set_zlim(-0.25, 1.25)

x1_grid, x2_grid = np.meshgrid(np.linspace(-0.25, 1.25, 10), np.linspace(-0.25, 1.25, 10))
y_grid = np.empty([10, 10])

plot.plot(x_train[:, 0].squeeze(), x_train[:, 1].squeeze(), y_train[:, 0].squeeze(),
          'o', color='blue', label='$(x_1^{(i)},x_2^{(i)},y^{(i)})$')

plot_f = plot.plot_wireframe(np.array([[]]), np.array([[]]), np.array([[]]), color="green",
                             label="$\\hat y=f(\\mathbf{x})=\\sigma(\\mathbf{xW}+b)$")
for i in range(0, x1_grid.shape[0]):
    for j in range(0, x1_grid.shape[1]):
        y_grid[i, j] = model.f([[x1_grid[i, j], x2_grid[i, j]]])
plot.plot_wireframe(x1_grid, x2_grid, y_grid, color='green', alpha=0.75)

table = plt.table(cellText=[[0, 0, 1], [0, 1, 0], [1, 0, 0], [1, 1, 0]],
                  colWidths=[0.1] * 3,
                  colLabels=["$x_1$", "$x_2$", "$f(\\mathbf{x})$"],
                  cellLoc="center",
                  loc="upper right")

plot_info = fig.text(0.01, 0.02, "W = %s\nb = %s\nloss = %f" % (model.W, model.b, model.loss(x_train, y_train)))

plot.legend(loc='upper left')

plt.show()
