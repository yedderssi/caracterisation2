#ifndef AMPLI_H
#define AMPLI_H

#include <QDialog>

namespace Ui {
class Ampli;
}

class Ampli : public QDialog
{
    Q_OBJECT

public:
    explicit Ampli(QWidget *parent = nullptr);
    ~Ampli();

private:
    Ui::Ampli *ui;
};

#endif // AMPLI_H
